import re
import json
import random
import textwrap
from typing import Any
from datasets import Dataset

from stream_bench.benchmarks.base import Bench
from stream_bench.benchmarks.utils import extract_json_string, strip_all_lines
from stream_bench.benchmarks.toolbench_utils import fewshots
from stream_bench.llms.oai_chat import OpenAIChat

API_NAME2DESC = {
    "add_date": "Add days to a date. Date should be pass as 'yyyy-mm-dd'.. Your input should be a json (args json schema): {{\"date\" : string, \"days\" : integer, }} The Action to trigger this API should be add_date and the input parameters should be a json dict string. Pay attention to the type of parameters.",
    "BART%%Advisory information": "{\"description\": \"\", \"required_parameters\": [{\"name\": \"cmd\", \"type\": \"STRING\", \"description\": \"See more examples http://api.bart.gov/docs/overview/examples.aspx\", \"default\": \"bsa\"}], \"optional_parameters\": [{\"name\": \"orig\", \"type\": \"STRING\", \"description\": \"Optional station filter. Uses 4 character BART station abbreviations (http://api.bart.gov/docs/overview/abbrev.aspx)\", \"default\": \"\"}], \"parent_tool_name\": \"BART\", \"parent_tool_description\": \"The BART API gives you access to pretty much all of the BART service and station data available on the BART website.\"}",
    "Car database%%Makes": "{\"description\": \"Return all makes\", \"required_parameters\": [], \"optional_parameters\": [], \"parent_tool_name\": \"Car database\", \"parent_tool_description\": \"Database of car makes and models\"}",
    "CatchLoc%%[Group Management] API access for modifying group information": "{\"description\": \"API access to modifying location object's group information\\n\\nrequired parameter : api (api.common.group.set.modify)\", \"required_parameters\": [{\"name\": \"timestamp\", \"type\": \"STRING\", \"description\": \"\", \"default\": \"\"}, {\"name\": \"api_key\", \"type\": \"STRING\", \"description\": \"\", \"default\": \"\"}, {\"name\": \"group_name\", \"type\": \"STRING\", \"description\": \"\", \"default\": \"\"}, {\"name\": \"api\", \"type\": \"STRING\", \"description\": \"\", \"default\": \"\"}, {\"name\": \"cert_key\", \"type\": \"STRING\", \"description\": \"\", \"default\": \"\"}, {\"name\": \"group_key\", \"type\": \"STRING\", \"description\": \"\", \"default\": \"\"}], \"optional_parameters\": [], \"parent_tool_name\": \"CatchLoc\", \"parent_tool_description\": \"[For Gper Owner Only] Catchloc is a platform that controls the location and information collected by spacosa's devices.\"}",
    "colegiosantaana%%Disciplina-1": "{\"description\": \"Disciplina alumno 1\", \"required_parameters\": [], \"optional_parameters\": [], \"parent_tool_name\": \"colegiosantaana\", \"parent_tool_description\": \"Colegio Santa Ana\"}",
    "colegiosantaana%%Evaluaciones-1": "{\"description\": \"Evaluaciones alumno 1\", \"required_parameters\": [], \"optional_parameters\": [], \"parent_tool_name\": \"colegiosantaana\", \"parent_tool_description\": \"Colegio Santa Ana\"}",
    "colegiosantaana%%Mensajes-1": "{\"description\": \"Mensajes del alumno 1\", \"required_parameters\": [], \"optional_parameters\": [], \"parent_tool_name\": \"colegiosantaana\", \"parent_tool_description\": \"Colegio Santa Ana\"}",
    "disambiguation": "The input is an entity name. This action will disambiguate this entity name to find other entities with similar names in Wikipedia.. Your input should be a json (args json schema): {{\"entity\" : string, }} The Action to trigger this API should be disambiguation and the input parameters should be a json dict string. Pay attention to the type of parameters.",
    "English Talking%%Get an answer": "{\"description\": \"Get an answer\", \"required_parameters\": [], \"optional_parameters\": [{\"name\": \"status\", \"type\": \"STRING\", \"description\": \"approved or analyzing\", \"default\": \"approved\"}, {\"name\": \"answer\", \"type\": \"STRING\", \"description\": \"Response to the initial speech of the dialogue\", \"default\": \"Hi, how are you?\"}, {\"name\": \"_id\", \"type\": \"STRING\", \"description\": \"Unique dialog identifier (automatically generated)\\n\\n\", \"default\": \"5ec47b3d8958430d6a6d5898\"}, {\"name\": \"speech\", \"type\": \"STRING\", \"description\": \"Speak in which the usuairio wants to get an answer\", \"default\": \"Hi\"}, {\"name\": \"user\", \"type\": \"STRING\", \"description\": \"User who created the dialogue\", \"default\": \"5ec479048958430d6a6d5895\"}], \"parent_tool_name\": \"English Talking\", \"parent_tool_description\": \"This API aims to provide users with the possibility of conducting dialogues in English where the conversations and answers are registered and evaluated by the users themselves.\\n\\ud83d\\udc7d\"}",
    "F1 Latest News%%GET recent F1 news from all sources": "{\"description\": \"This endpoint returns back recent articles from all sources\", \"required_parameters\": [], \"optional_parameters\": [], \"parent_tool_name\": \"F1 Latest News\", \"parent_tool_description\": \"This API scrapes the most recent F1 news articles from, the official F1 website, Sky F1, BBC F1, WTF1, and Autosport. More may be added in the future...\"}",
    "Fake Brightcove%%Temp Upload URLs": "{\"description\": \"Generate Temp Upload URLs\", \"required_parameters\": [{\"name\": \"source_name\", \"type\": \"string\", \"description\": \"\", \"default\": \"\"}, {\"name\": \"video_id\", \"type\": \"string\", \"description\": \"\", \"default\": \"\"}, {\"name\": \"account_id\", \"type\": \"string\", \"description\": \"\", \"default\": \"\"}], \"optional_parameters\": [], \"parent_tool_name\": \"Fake Brightcove\", \"parent_tool_description\": \"Fake Brightcove API\"}",
    "Fluximmo%%get_portail_api": "{\"description\": \" \", \"required_parameters\": [], \"optional_parameters\": [], \"parent_tool_name\": \"Fluximmo\", \"parent_tool_description\": \"API de flux immobilier \\ud83c\\udfe1: Scraper LEBONCOIN, PAP, EXPLORIMMO, MEILLEURSAGENTS et plus de 20 portails - Cr\\u00e9ez des services innovants gr\\u00e2ce \\u00e0 notre flux d'annonces immobili\\u00e8res en temps r\\u00e9el !\"}",
    "Football Dolphin%%Head to head statistics": "{\"description\": \"Head to head statistics\", \"required_parameters\": [{\"name\": \"first_team\", \"type\": \"STRING\", \"description\": \"**Enter first team from all available teams:** Arsenal, Aston Villa, Barnsley, Birmingham, Blackburn, Blackpool, Bolton, Bournemouth, Bradford, Brighton, Burnley, Cardiff, Charlton, Chelsea, Coventry, Crystal Palace, Derby, Everton, Fulham, Huddersfield, Hull, Ipswich, Leeds, Leicester, Liverpool, Man City, Man United, Middlesbrough, Newcastle, Norwich, Nott'm Forest, Portsmouth, QPR, Reading, Sheffield United, Sheffield Weds, Southampton, Stoke, Sunderland, Swansea, Tottenham, Watford, West Brom, West Ham, Wigan, Wimbledon, Wolves\", \"default\": \"Man United\"}, {\"name\": \"second_team\", \"type\": \"STRING\", \"description\": \"**Enter second team from all available teams:** Arsenal, Aston Villa, Barnsley, Birmingham, Blackburn, Blackpool, Bolton, Bournemouth, Bradford, Brighton, Burnley, Cardiff, Charlton, Chelsea, Coventry, Crystal Palace, Derby, Everton, Fulham, Huddersfield, Hull, Ipswich, Leeds, Leicester, Liverpool, Man City, Man United, Middlesbrough, Newcastle, Norwich, Nott'm Forest, Portsmouth, QPR, Reading, Sheffield United, Sheffield Weds, Southampton, Stoke, Sunderland, Swansea, Tottenham, Watford, West Brom, West Ham, Wigan, Wimbledon, Wolves\", \"default\": \"Liverpool\"}, {\"name\": \"type_of_statistics\", \"type\": \"STRING\", \"description\": \"**Enter one from available types of statistics:** \\nfull time result, \\nhome vs away full time result, \\nresult first half and the match,\\nexact number of goals in the match, \\ngoals over, \\ngoals under\", \"default\": \"full time result\"}], \"optional_parameters\": [], \"parent_tool_name\": \"Football Dolphin\", \"parent_tool_description\": \"This Api returns statistical data about English Premier League. Click on the link to view all endpoints in one web app  https://football-dolphin-web-app.up.railway.app/\"}",
    "forecast_weather": "Forecast weather in the upcoming days.. Your input should be a json (args json schema): {{\"location\" : string, \"days\" : integer, }} The Action to trigger this API should be forecast_weather and the input parameters should be a json dict string. Pay attention to the type of parameters.",
    "GamerPower%%Filter & Group Giveaways": "{\"description\": \"Filter and group platforms and giveaway types to get personalized results.\", \"required_parameters\": [{\"name\": \"platform\", \"type\": \"STRING\", \"description\": \"\", \"default\": \"epic-games-store.steam.android\"}], \"optional_parameters\": [{\"name\": \"type\", \"type\": \"STRING\", \"description\": \"\", \"default\": \"game.loot\"}], \"parent_tool_name\": \"GamerPower\", \"parent_tool_description\": \"Find all free games, loot and giveaways with this giveaway tracker API powered by GamerPower.com! Access programmatically the best giveaways in gaming!\"}",
    "GamerPower%%Live giveaways by type": "{\"description\": \"Get live giveaways by type, eg: game, loot, beta\", \"required_parameters\": [{\"name\": \"type\", \"type\": \"STRING\", \"description\": \"\", \"default\": \"game\"}], \"optional_parameters\": [], \"parent_tool_name\": \"GamerPower\", \"parent_tool_description\": \"Find all free games, loot and giveaways with this giveaway tracker API powered by GamerPower.com! Access programmatically the best giveaways in gaming!\"}",
    "getWolframAlphaResults": "Get Wolfram|Alpha results using natural query, which could be about Mathematics (e.g., Algebra, Geometry, Statistics, Number Theory), Science & Technology (e.g., Physics, Chemistry, Earth Sciences, Life Sciences, Space & Astronomy), Society & Culture (e.g., Arts & Media, History, Words & Linguistics, Money & Finance) and Everyday life (Health, Finance, Entertainment, Today's World). Queries to getWolframAlphaResults must ALWAYS have this structure: {{\"input\": query}}. And please directly read the output json.. Your input should be a json (args json schema): {{\"input\" : string, }} The Action to trigger this API should be getWolframAlphaResults and the input parameters should be a json dict string. Pay attention to the type of parameters.",
    "get_arxiv_article_information": "Run Arxiv search and get the article meta information.. Your input should be a json (args json schema): {{\"query\" : string, }} The Action to trigger this API should be get_arxiv_article_information and the input parameters should be a json dict string. Pay attention to the type of parameters.",
    "get_today_date": "Get today's date.  The Action to trigger this API should be get_today_date and the input parameters should be a json dict string. Pay attention to the type of parameters.",
    "get_weather_today": "Get today's the weather. Your input should be a json (args json schema): {{\"location\" : string, }} The Action to trigger this API should be get_weather_today and the input parameters should be a json dict string. Pay attention to the type of parameters.",
    "Global Email V4%%Global Email V4": "{\"description\": \"Define Input Fields\", \"required_parameters\": [{\"name\": \"opt\", \"type\": \"STRING\", \"description\": \"Express/Premium\", \"default\": \"VerifyMailbox:Express|VerifyMailbox:ExpressPremium\"}, {\"name\": \"email\", \"type\": \"STRING\", \"description\": \"Input Email\", \"default\": \"support@melissa.com\"}], \"optional_parameters\": [{\"name\": \"format\", \"type\": \"STRING\", \"description\": \"Format of Response\", \"default\": \"json\"}], \"parent_tool_name\": \"Global Email V4\", \"parent_tool_description\": \"Easily verify, check or lookup email. Global Email JSON API provides real-time email mailbox checking including domain-specific logic, SMTP commands and other proprietary mechanisms to validate that inboxes are live using a cached inbox validation database of known good and bad emails.\"}",
    "Grup Terbuka%%Kirim Pesan": "{\"description\": \"api untuk kirim pesan\", \"required_parameters\": [{\"name\": \"pesan\", \"type\": \"STRING\", \"description\": \"\", \"default\": \"pesan baru\"}, {\"name\": \"key\", \"type\": \"STRING\", \"description\": \"\", \"default\": \"\"}], \"optional_parameters\": [], \"parent_tool_name\": \"Grup Terbuka\", \"parent_tool_description\": \"open api group chat\"}",
    "Handball Data%%Daily Match List-Live": "{\"description\": \"Daily match list including live matches.\\n\\n**The data will return for only -+7 days period, so endpoint can be tested with date range of today - 7 days.**\", \"required_parameters\": [{\"name\": \"date\", \"type\": \"STRING\", \"description\": \"The date of the match. The format is {dd/MM/yyyy}. Match list data can be retrieved for only \\u00b1 7 days.\", \"default\": \"28/01/2021\"}], \"optional_parameters\": [], \"parent_tool_name\": \"Handball Data\", \"parent_tool_description\": \"Broadage Handball API will give you wide range of data of world's top handball leagues, including fixtures, standings, match lists and many more. Our Handball Coverage includes the biggest handball tournaments from all around the world with in-depth coverage, giving you the opportunity to present the best sports data to users located anywhere.<br>This is a limited version in RapidApi. <a href=\\\"https://www.broadage.com/signup/api/free?utm_source=rapidapi&utm_medium=click&utm_campaign=handball_api\\\" target=\\u201d_blank\\u201d>Please, click here to start your Free Trial and try the endpoints with live data now!</a>\"}",
    "Handball Data%%Daily Match List-Scheduled": "{\"description\": \"Daily match list including scheduled matches.\\n\\n**The data will return for only -+7 days period, so endpoint can be tested with date range of today - 7 days.**\", \"required_parameters\": [{\"name\": \"date\", \"type\": \"STRING\", \"description\": \"The date of the match. The format is {dd/MM/yyyy}. Match list data can be retrieved for only \\u00b1 7 days.\", \"default\": \"28/01/2021\"}], \"optional_parameters\": [], \"parent_tool_name\": \"Handball Data\", \"parent_tool_description\": \"Broadage Handball API will give you wide range of data of world's top handball leagues, including fixtures, standings, match lists and many more. Our Handball Coverage includes the biggest handball tournaments from all around the world with in-depth coverage, giving you the opportunity to present the best sports data to users located anywhere.<br>This is a limited version in RapidApi. <a href=\\\"https://www.broadage.com/signup/api/free?utm_source=rapidapi&utm_medium=click&utm_campaign=handball_api\\\" target=\\u201d_blank\\u201d>Please, click here to start your Free Trial and try the endpoints with live data now!</a>\"}",
    "JAK_API%%Ben 10": "{\"description\": \"Get the JSON formatted data about Ben 10!!\", \"required_parameters\": [], \"optional_parameters\": [], \"parent_tool_name\": \"JAK_API\", \"parent_tool_description\": \"A API made by Jonak Adipta Kalita!!\"}",
    "JAK_API%%Brawl Stars": "{\"description\": \"Get the JSON formated file containing details about Brawl Stars!!\", \"required_parameters\": [], \"optional_parameters\": [], \"parent_tool_name\": \"JAK_API\", \"parent_tool_description\": \"A API made by Jonak Adipta Kalita!!\"}",
    "JAK_API%%Genshin Impact": "{\"description\": \"Get the JSON formatted data about Genshin Impact\", \"required_parameters\": [], \"optional_parameters\": [], \"parent_tool_name\": \"JAK_API\", \"parent_tool_description\": \"A API made by Jonak Adipta Kalita!!\"}",
    "JAK_API%%Miraculous": "{\"description\": \"Get the JSON formated file containing details about Miraculous!!\", \"required_parameters\": [], \"optional_parameters\": [], \"parent_tool_name\": \"JAK_API\", \"parent_tool_description\": \"A API made by Jonak Adipta Kalita!!\"}",
    "Marvel Vs Capcom 2%%All Characters": "{\"description\": \"Access all characters in MVC2 (Marvel Vs Capcom) Universe\", \"required_parameters\": [], \"optional_parameters\": [], \"parent_tool_name\": \"Marvel Vs Capcom 2\", \"parent_tool_description\": \"Get data about  characters from Marvel Vs Capcom 2 game.\"}",
    "Marvel Vs Capcom 2%%Show Character": "{\"description\": \"Get details about a single character and their traits\", \"required_parameters\": [{\"name\": \"name\", \"type\": \"string\", \"description\": \"\", \"default\": \"Cabel\"}], \"optional_parameters\": [], \"parent_tool_name\": \"Marvel Vs Capcom 2\", \"parent_tool_description\": \"Get data about  characters from Marvel Vs Capcom 2 game.\"}",
    "MikuAPI%%getRandomImage": "{\"description\": \" \", \"required_parameters\": [], \"optional_parameters\": [], \"parent_tool_name\": \"MikuAPI\", \"parent_tool_description\": \"An API that provides you with Images of the popular Japanese Popstar Hatsune Miku. \"}",
    "Numbers Translator%%Numbers Translator": "{\"description\": \"Numbers Translator\", \"required_parameters\": [], \"optional_parameters\": [{\"name\": \"text\", \"type\": \"STRING\", \"description\": \"Numerical value of the number\", \"default\": \"23879908709817834\"}], \"parent_tool_name\": \"Numbers Translator\", \"parent_tool_description\": \"Convert numerical numbers to words. For example 23879908709817834 will give you \\\"Twenty-three quadrillion eight hundred seventy-nine trillion nine hundred eight billion seven hundred nine million eight hundred seventeen thousand eight hundred thirty-four\\\".\"}",
    "Numbers%%Get math fact": "{\"description\": \"Get a mathematical property about a number\", \"required_parameters\": [{\"name\": \"number\", \"type\": \"STRING\", \"description\": \"The integer of interest\", \"default\": \"1729\"}], \"optional_parameters\": [{\"name\": \"fragment\", \"type\": \"STRING\", \"description\": \"Add \\\"?fragment=true\\\" to return the fact as a sentence fragment that can be easily included as part of a larger sentence. This means that the first word is lowercase and ending punctuation is omitted. For trivia and math, a noun phrase is returned that can be used in a sentence like \\u201cWe now have more users than [fact as fragment]!\\u201d.\", \"default\": true}, {\"name\": \"json\", \"type\": \"STRING\", \"description\": \"Specify \\\"true\\\" to return result as JSON instead of plaintext.\", \"default\": true}], \"parent_tool_name\": \"Numbers\", \"parent_tool_description\": \"An API for interesting facts about numbers. Provides trivia, math, date, and year facts about numbers. \\r\\n\\r\\nFor example, \\\"5 is the number of platonic solids\\\", \\\"42 is the number of little squares forming the left side trail of Microsoft's Windows 98 logo\\\", \\\"February 27th is the day in 1964 that the government of Italy asks for help to keep the Leaning Tower of Pisa from toppling over\\\"\"}",
    "NumbersToLetters%%Convertir cantidad a letra Moneda MXN Español": "{\"description\": \"Convierte de cantidad a letras pesos Mexicano EndPoind Espa\\u00f1ol\\nSe agrego el parametro **moneda**, los tipos aceptados para este parametro son los siguientes (PESOS, DOLARES, EUROS), TODO EN MAYUSCULAS.\", \"required_parameters\": [{\"name\": \"moneda\", \"type\": \"STRING\", \"description\": \"\", \"default\": \"DOLARES\"}, {\"name\": \"monto\", \"type\": \"STRING\", \"description\": \"\", \"default\": \"1000\"}], \"optional_parameters\": [], \"parent_tool_name\": \"NumbersToLetters\", \"parent_tool_description\": \"Convierte cantidad a letras peso Mexicano, Espa\\u00f1ol e Ingles\"}",
    "NumbersToLetters%%Convertir cantidad a letra Moneda MXN Ingles": "{\"description\": \"Convertir cantidad a letra Moneda MXN en Ingles\", \"required_parameters\": [{\"name\": \"moneda\", \"type\": \"STRING\", \"description\": \"\", \"default\": \"DOLARES\"}, {\"name\": \"monto\", \"type\": \"STRING\", \"description\": \"\", \"default\": \"1000\"}], \"optional_parameters\": [], \"parent_tool_name\": \"NumbersToLetters\", \"parent_tool_description\": \"Convierte cantidad a letras peso Mexicano, Espa\\u00f1ol e Ingles\"}",
    "Password Generator API%%Base": "{\"description\": \"Only this endpoint is currently supported which gives you a random password\", \"required_parameters\": [], \"optional_parameters\": [], \"parent_tool_name\": \"Password Generator API\", \"parent_tool_description\": \"This API generate cryptographically random strong password which are nearly impossible to break\"}",
    "Password Generator API%%Password of length 50": "{\"description\": \"Gives you length 50 password\", \"required_parameters\": [], \"optional_parameters\": [{\"name\": \"length\", \"type\": \"STRING\", \"description\": \"\", \"default\": \"50\"}], \"parent_tool_name\": \"Password Generator API\", \"parent_tool_description\": \"This API generate cryptographically random strong password which are nearly impossible to break\"}",
    "pizzaallapala%%Get Producto Promo": "{\"description\": \"Adsa\", \"required_parameters\": [], \"optional_parameters\": [], \"parent_tool_name\": \"pizzaallapala\", \"parent_tool_description\": \"api fake to test frontend\"}",
    "Places%%Geographic coordinates by placename": "{\"description\": \"Returns geographic coordinates for the given placename (city, village, etc.). The method returns the place whose name is most similar to the search string.\", \"required_parameters\": [{\"name\": \"name\", \"type\": \"STRING\", \"description\": \"Placename\", \"default\": \"London\"}, {\"name\": \"lang\", \"type\": \"ENUM\", \"description\": \"Two-letter language code (ISO639-1). The following values are available: en (english), ru (russian)\", \"default\": \"\"}], \"optional_parameters\": [{\"name\": \"country\", \"type\": \"STRING\", \"description\": \"Two-letter country code, ISO-3166 (optional). Default is all countries.\", \"default\": \"\"}], \"parent_tool_name\": \"Places\", \"parent_tool_description\": \"Over 10 million tourist attractions and facilities around the world\"}",
    "PTL%%update": "{\"description\": \"update endpoint\", \"required_parameters\": [{\"name\": \"info3\", \"type\": \"STRING\", \"description\": \"\", \"default\": \"333\"}, {\"name\": \"info1\", \"type\": \"STRING\", \"description\": \"\", \"default\": \"111\"}, {\"name\": \"info2\", \"type\": \"STRING\", \"description\": \"\", \"default\": \"222\"}], \"optional_parameters\": [], \"parent_tool_name\": \"PTL\", \"parent_tool_description\": \"receive user\"}",
    "search": "The input is an exact entity name. The action will search this entity name on Wikipedia and returns the first five sentences if it exists. If not, it will return some related entities to search next.. Your input should be a json (args json schema): {{\"entity\" : string, }} The Action to trigger this API should be search and the input parameters should be a json dict string. Pay attention to the type of parameters.",
    "search_general": "Run query through GoogleSearch and parse result.. Your input should be a json (args json schema): {{\"query\" : string, }} The Action to trigger this API should be search_general and the input parameters should be a json dict string. Pay attention to the type of parameters.",
    "search_places": "Run Places search.. Your input should be a json (args json schema): {{\"query\" : string, }} The Action to trigger this API should be search_places and the input parameters should be a json dict string. Pay attention to the type of parameters.",
    "siteDomain%%industry list": "{\"description\": \"\\u7522\\u696d\\u5225\\u4e8c\\u78bc\", \"required_parameters\": [{\"name\": \"alias\", \"type\": \"string\", \"description\": \"\", \"default\": \"\"}], \"optional_parameters\": [], \"parent_tool_name\": \"siteDomain\", \"parent_tool_description\": \"site adm domain\"}",
    "siteDomain%%language list": "{\"description\": \"\\u7cfb\\u7d71\\u8a9e\\u7cfb\\u5217\\u8868\", \"required_parameters\": [], \"optional_parameters\": [], \"parent_tool_name\": \"siteDomain\", \"parent_tool_description\": \"site adm domain\"}",
    "Soccer Data%%Tournament List": "{\"description\": \"Provides list of tournaments.\", \"required_parameters\": [], \"optional_parameters\": [], \"parent_tool_name\": \"Soccer Data\", \"parent_tool_description\": \"Broadage Soccer API brings a wide range of data for Soccer in fixtures, livescores, standings and many more. Team, tournament or match, retrieve real time data for any perspective you need. Our Soccer Coverage includes 350+ tournaments from all around the world with in-depth coverage, giving the chance to present the best sports data from users located anywhere. <br>This is a limited version in RapidApi. <a href=\\\"https://www.broadage.com/signup/api/free?utm_source=rapidapi&utm_medium=click&utm_campaign=soccer_api\\\" target=\\u201d_blank\\u201d>Please, click here to start your Free Trial and try the endpoints with live data now!</a>\"}",
    "Stadia Maps Time Zone API%%TZ Lookup by Location": "{\"description\": \"The Stadia TZ Lookup API provides time zone information, as well as information about any special offset (such as DST) in effect based on the latest IANA TZDB. Note that this API may not be accurate for timestamps in the past and does not claim to report precise nautical times in the open ocean beyond territorial waters.\", \"required_parameters\": [{\"name\": \"lat\", \"type\": \"NUMBER\", \"description\": \"The latitude component of any point on land.\", \"default\": \"37.4666405\"}, {\"name\": \"lng\", \"type\": \"NUMBER\", \"description\": \"The longitude component of any point on land.\", \"default\": \"-85.89465\"}], \"optional_parameters\": [{\"name\": \"timestamp\", \"type\": \"NUMBER\", \"description\": \"The UNIX timestamp at which the UTC and DST offsets will be calculated. This defaults to the present time. This endpoint is not necessarily guaranteed to be accurate for timestamps that occurred in the past. Time zone geographic boundaries change over time, so if the point you are querying for was previously in a different time zone, historical results will not be accurate. If, however, the point has been in the same geographic time zone for a very long time (ex: America/New_York), the historical data may be accurate for 100+ years in the past (depending on how far back the IANA TZDB rules have been specified).\", \"default\": \"1589932800\"}], \"parent_tool_name\": \"Stadia Maps Time Zone API\", \"parent_tool_description\": \"The Stadia TZ API provides time zone information, as well as information about any special offset (such as DST) in effect, now or in the future.\"}",
    "thailand%%thai4": "{\"description\": \"thai4\", \"required_parameters\": [], \"optional_parameters\": [], \"parent_tool_name\": \"thailand\", \"parent_tool_description\": \"thailand\"}",
    "Token API%%generate": "{\"description\": \"Generate a new token for Language API\", \"required_parameters\": [], \"optional_parameters\": [], \"parent_tool_name\": \"Token API\", \"parent_tool_description\": \"Generate a new token for Unlimited Language API. Token is only valid for ~5 minuts, so it has to be generated frequently\"}",
    "Weather_dataSet%%Weather_dataSet": "{\"description\": \"Check The Weather Api Process\", \"required_parameters\": [], \"optional_parameters\": [{\"name\": \"data\", \"type\": \"STRING\", \"description\": \"Check The weather data into Weather_API Process\", \"default\": \"1\"}], \"parent_tool_name\": \"Weather_dataSet\", \"parent_tool_description\": \"Weather_data Set on Django Project\"}"
}

class ToolBench(Bench):
    DATASET_PATH = "appier-ai-research/StreamBench"
    DATASET_NAME = "toolbench"
    FEWSHOTS = fewshots.rows

    API_NAME_LIST = ["add_date", "BART%%Advisory information", "Car database%%Makes", "CatchLoc%%[Group Management] API access for modifying group information", "colegiosantaana%%Disciplina-1", "colegiosantaana%%Evaluaciones-1", "colegiosantaana%%Mensajes-1", "disambiguation", "English Talking%%Get an answer", "F1 Latest News%%GET recent F1 news from all sources", "Fake Brightcove%%Temp Upload URLs", "Fluximmo%%get_portail_api", "Football Dolphin%%Head to head statistics", "forecast_weather", "GamerPower%%Filter & Group Giveaways", "GamerPower%%Live giveaways by type", "getWolframAlphaResults", "get_arxiv_article_information", "get_today_date", "get_weather_today", "Global Email V4%%Global Email V4", "Grup Terbuka%%Kirim Pesan", "Handball Data%%Daily Match List-Live", "Handball Data%%Daily Match List-Scheduled", "JAK_API%%Ben 10", "JAK_API%%Brawl Stars", "JAK_API%%Genshin Impact", "JAK_API%%Miraculous", "Marvel Vs Capcom 2%%All Characters", "Marvel Vs Capcom 2%%Show Character", "MikuAPI%%getRandomImage", "Numbers Translator%%Numbers Translator", "Numbers%%Get math fact", "NumbersToLetters%%Convertir cantidad a letra Moneda MXN Español", "NumbersToLetters%%Convertir cantidad a letra Moneda MXN Ingles", "Password Generator API%%Base", "Password Generator API%%Password of length 50", "pizzaallapala%%Get Producto Promo", "Places%%Geographic coordinates by placename", "PTL%%update", "search", "search_general", "search_places", "siteDomain%%industry list", "siteDomain%%language list", "Soccer Data%%Tournament List", "Stadia Maps Time Zone API%%TZ Lookup by Location", "thailand%%thai4", "Token API%%generate", "Weather_dataSet%%Weather_dataSet"]
    EM_APIS = {'Handball Data%%Daily Match List-Scheduled', 'NumbersToLetters%%Convertir cantidad a letra Moneda MXN Español', 'Password Generator API%%Password of length 50', 'get_today_date', 'Football Dolphin%%Head to head statistics', 'Fluximmo%%get_portail_api', 'Numbers Translator%%Numbers Translator', 'NumbersToLetters%%Convertir cantidad a letra Moneda MXN Ingles', 'JAK_API%%Miraculous', 'forecast_weather', 'MikuAPI%%getRandomImage', 'JAK_API%%Ben 10', 'siteDomain%%language list', 'colegiosantaana%%Mensajes-1', 'thailand%%thai4', 'Token API%%generate', 'colegiosantaana%%Evaluaciones-1', 'Car database%%Makes', 'Marvel Vs Capcom 2%%All Characters', 'add_date', 'JAK_API%%Brawl Stars', 'Global Email V4%%Global Email V4', 'Soccer Data%%Tournament List', 'colegiosantaana%%Disciplina-1', 'Places%%Geographic coordinates by placename', 'JAK_API%%Genshin Impact', 'BART%%Advisory information', 'Password Generator API%%Base', 'Numbers%%Get math fact', 'pizzaallapala%%Get Producto Promo', 'F1 Latest News%%GET recent F1 news from all sources'}
    assert (len(API_NAME_LIST) == 50) and (len(set(API_NAME_LIST) | EM_APIS) == 50)
    random.seed(0)
    random.shuffle(API_NAME_LIST)
    api_docs = "\n\n        ".join([f'API_name: {api_name}\n        Description: {API_NAME2DESC[api_name]}' for api_name in API_NAME_LIST])
    api_names = "\n        ".join(API_NAME_LIST)

    def __init__(
        self,
        split: str = "test",
        seed: int = 0,
        feedback: str = "no_user_feedback",
        **kwargs
    ) -> None:
        super().__init__({})
        print("Finish loading the ToolBench dataset.")
        self.split = split
        self.seed = seed
        self.feedback = feedback
        self.n_api_correct = 0
        self.n_args_correct = 0
        self.llm = OpenAIChat(model_name="gpt-3.5-turbo-0125")
        self.fewshot_text = self.get_fewshot_text()

    def get_dataset(self) -> Dataset:
        return self.dataset[self.split].shuffle(seed=self.seed)    

    def get_input(self, row: dict) -> dict:
        row_input = {key: row[key].strip() for key in ["query"]}
        row_input["question"] = row["query"]
        row_input["prompt_zeroshot"] = self.get_zeroshot_prompt(query=row["query"])
        row_input["prompt_fewshot"] = self.get_fewshot_prompt(query=row["query"])
        row_input["prompt_cot"] = self.get_cot_prompt(query=row["query"])
        row_input["fewshot_template"] = self.get_fewshot_template(query=row["query"])
        row_input["feedback_template"] = self.get_feedback_template(query=row["query"])
        row_input["refine_template"] = self.get_refine_template(query=row["query"])
        return row_input

    def get_output(self, row: dict) -> dict:        
        return {
            "api_name": row["api_name"],
            "api_input": row["api_input"]
        }

    def postprocess_generation(self, res: str, idx: int) -> dict:
        json_str = extract_json_string(res)
        try:
            res_json = json.loads(json_str)
            res_json["parse_successful"] = 1
        except json.JSONDecodeError:
            res_json = {
                "action": "None",
                "action_input": dict(),
                "parse_successful": 0
            }
            print(f"Fail to parse json string from ```{res}```")
        if not (("action" in res_json) and ("action_input" in res_json)):
            res_json = {
                "action": "None",
                "action_input": dict(),
                "parse_successful": 0
            }
            print(f"Fail to find 'action' and 'action_input' in json string from ```{res}```")
        return res_json

    def process_results(self, prediction: dict, label: dict, return_details: bool = True, **kwargs) -> bool | dict:
        # if not prediction["parse_successful"]:
        #     raise ValueError("parsing not successful")

        # Variables to return
        correct = 0
        api_correct = 0
        args_correct = 0
        
        gt_api = label["api_name"]
        gt_args = label["api_input"]
        
        model_api = prediction["action"]
        model_args = prediction["action_input"]
        
        # check API name
        if gt_api == model_api:
            api_correct = 1
            # check API args
            args_correct = self.check_api_args(gt_api, gt_args, model_api, model_args)

        if (api_correct == 1) and (args_correct == 1):
            correct = 1        
        self.n_correct += correct
        self.n_api_correct += api_correct
        self.n_args_correct += args_correct
        self.references.append(label)
        if return_details:
            return {
                "correct": correct,
                "api_correct": api_correct,
                "args_correct": args_correct,
                "n_correct": self.n_correct,
                "n_api_correct": self.n_api_correct,
                "n_args_correct": self.n_args_correct,
                "rolling_acc": self.n_correct / len(self.references),
                "parse_successful": prediction["parse_successful"]
            }
        return correct

    def get_metrics(self) -> dict:
        return {
            "api_accuracy": self.n_api_correct / len(self.references),
            "accuracy": self.n_correct / len(self.references)
        }

    def give_feedback(self, model_output: str, row: dict, res: dict) -> tuple[bool, dict]:
        d = self.postprocess_generation(model_output, idx=-1)
        pred_str = json.dumps({"action": d["action"], "action_input": d["action_input"]})
        has_feedback = True
        feedbacks = {
            "question": row["query"],
            "self_output": pred_str,
            "is_correct": res["correct"],
            "ground_truth": json.dumps({"action": row["api_name"], "action_input": row["api_input"]}),
            "shot_template": self.get_shot_template(),
            "memprompt_template": self.get_memprompt_template()
        }
        return has_feedback, feedbacks

    def check_api_args(
        self,
        gt_api: str,
        gt_args: str,
        model_api: str,
        model_args: str
    ):
        args_correct = 1
        if gt_api in self.EM_APIS:  # if the api_args need to be exactly matched
            if isinstance(gt_args, str):
                gt_args = json.loads(gt_args)
            if isinstance(model_args, str):
                model_args = json.loads(model_args)
            for k, v in gt_args.items():
                if (k not in model_args) or (str(model_args[k]).strip().lower() != str(v).strip().lower()):
                    args_correct = 0
                    break
        else:
            prompt = textwrap.dedent(f"""\
            Your task is to judge whether an API call is correct with respect to the given ground truth API call. Note that the API call doesn't have to be exactly the same as the ground truth; it only needs to be semantically correct. It should not miss any important details in the arguments.
            
            The ground truth API call is:
            API name: {gt_api}
            API arguments: {gt_args}
            
            The API call that you need to verify the correctness is:
            API name: {model_api}
            API arguments: {model_args}
            
            Now say your judgment. Your response should always start with \"Yes.\" or \"No.\" indicating whether it's correct.
            Your response:""")
            res_text, _ = self.llm(prompt, max_tokens=4, temperature=0)
            if "No." in res_text:
                args_correct = 0
        return args_correct

    def get_zeroshot_prompt(self, query: str) -> str:
        prompt = textwrap.dedent(f"""\
        Your task is to answer the user's query as best you can. You have access to the following tools which you can use via API call:

        {self.api_docs}

        The format you use the tools is by specifying
        1) action: the API function name you'd like to call
        2) action_input: the input parameters of the API call in a json string format.
        Remember that you should only perform a SINGLE action at a time, do NOT return a list of multiple actions.
        Provide your output in the JSON format of {{"action": <api_name>, "action_input": <api_arguments>}}.

        Important reminders:
        1) The only values that is valid for <api_name> are:
        {self.api_names}

        2) Use the following JSON string format for the <api_arguments>:
        {{"key_1": "value_1", ..., "key_n": "value_n"}}

        3) Remember to ALWAYS use the following format:
        {{"action": <api_name>, "action_input": <api_arguments>}}
        
        User Query: {query}.
        Now, only output {{"action": "<api_name>", "action_input": <api_arguments>}} as your answer.""")
        return strip_all_lines(prompt)

    def get_cot_prompt(self, query: str) -> str:
        prompt = textwrap.dedent(f"""\
        Your task is to answer the user's query as best you can. You have access to the following tools which you can use via API call:

        {self.api_docs}

        The format you use the tools is by specifying
        1) action: the API function name you'd like to call
        2) action_input: the input parameters of the API call in a json string format.
        Remember that you should only perform a SINGLE action at a time, do NOT return a list of multiple actions.
        Provide your answer in the JSON format of {{"action": <api_name>, "action_input": <api_arguments>}}.

        Important reminders:
        1) The only values that is valid for <api_name> are:
        {self.api_names}

        2) Use the following JSON string format for the <api_arguments>:
        {{"key_1": "value_1", ..., "key_n": "value_n"}}

        3) Remember to ALWAYS use the following format:
        {{"action": <api_name>, "action_input": <api_arguments>}}
        
        User Query: {query}.
        Now, take a deep breath and work on this problem step-by-step.
        Provide your output in the following format:
        Rationale: <your_rationale>
        Answer: {{"action": <api_name>, "action_input": <api_arguments>}}""")
        return strip_all_lines(prompt)

    def get_fewshot_template(self, query: str) -> str:
        prompt = textwrap.dedent(f"""\
        Your task is to answer the user's query as best you can. You have access to the following tools which you can use via API call:

        {self.api_docs}

        The format you use the tools is by specifying
        1) action: the API function name you'd like to call
        2) action_input: the input parameters of the API call in a json string format.
        Remember that you should only perform a SINGLE action at a time, do NOT return a list of multiple actions.
        Provide your output in the JSON format of {{"action": <api_name>, "action_input": <api_arguments>}}.

        Important reminders:
        1) The only values that is valid for <api_name> are:
        {self.api_names}

        2) Use the following JSON string format for the <api_arguments>:
        {{"key_1": "value_1", ..., "key_n": "value_n"}}

        3) Remember to ALWAYS use the following format:
        {{"action": <api_name>, "action_input": <api_arguments>}}
        
        Below are some examples:
        
        {{fewshot_text}}
        
        Now it's your turn.
        
        User Query: {query}.
        Now, only output {{"action": <api_name>, "action_input": <api_arguments>}} as your answer.""")
        return strip_all_lines(prompt)

    def get_fewshot_prompt(self, query: str) -> str:
        fewshot_template = self.get_fewshot_template(query)
        return re.sub(pattern=r"\{fewshot_text\}", repl=self.fewshot_text, string=fewshot_template)

    def get_fewshot_text(self) -> str:
        """
        feedbacks = {
            "question": row["query"],
            "ground_truth": json.dumps({"action": row["api_name"], "action_input": row["api_input"]}),
            "shot_template": self.get_shot_template(),
        }
        """
        assert len(self.FEWSHOTS) == 16
        shots = list()
        for row in self.FEWSHOTS:
            shot = self.get_shot_template().format(
                question=row["query"],
                answer=json.dumps({"action": row["action"], "action_input": row["action_input"]})
            )
            shots.append(shot)
        return "\n\n\n".join(shots).replace("\\", "\\\\")

    def get_shot_template(self) -> str:
        prompt = textwrap.dedent(f"""\
        User Query: {{question}}
        {{answer}}""")
        return prompt

    def get_memprompt_template(self) -> str:
        prompt = textwrap.dedent(f"""\
        User Query: {{question}}
        Your Answer: {{answer}}
        User Feedback: {{correctness}}""")
        return prompt

    def get_feedback_template(self, query: str) -> str:
        prompt = textwrap.dedent(f"""\
        Your task is to answer the user's query using the available tools via API call.
        Here are the API documents and the list of valid API function names.
        -- API Documentation: {self.api_docs}
        -- Valid API function names: {self.api_names}
        -- User Query: {query}
        -- Your previous API call: {{"action": "{{action_name}}", "action_input": {{action_input}}}}
        First, determine whether you need to refine your API call.
        If you consider that your API call is correct, output 'NO NEED TO REFINE' in uppercase.
        Otherwise, provide a suggestion to correct the API call.""")
        return strip_all_lines(prompt)

    def get_refine_template(self, query: str) -> str:
        """Note: The format of answer-feedback trajectory should be as follows
        Answer 0: <API_call_0>
        Feedback 0: <feedback_0>
        Answer 1: <API_call_1>
        Feedback 1: <feedback_1>
        ...
        Answer k: <API_call_k>
        Feedback k: <feedback_k>
        """
        prompt = textwrap.dedent(f"""\
        Your task is to answer the user's query using the available tools via API call.
        Here are the API documents, the list of valid API function names, and your previous answer-feedback trajectory.
        -- API Documentation: {self.api_docs}
        -- Valid API function names: {self.api_names}
        -- User Query: {query}
        -- Your previous answer-feedback trajectory:
        {{trajectory}}
        According to the latest feedback, provide your refined API call.
        Provide your output in the following format: {{"action": <api_name>, "action_input": <api_arguments>}}""")
        return strip_all_lines(prompt)
