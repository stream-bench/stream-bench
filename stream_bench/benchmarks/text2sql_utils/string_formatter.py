import re
import sqlite3

def nice_look_table(column_names: list, values: list):
    rows = []
    # Determine the maximum width of each column
    widths = [max(len(str(value[i])) for value in values + [column_names]) for i in range(len(column_names))]

    # Print the column names
    header = ''.join(f'{column.rjust(width)} ' for column, width in zip(column_names, widths))
    # print(header)
    # Print the values
    for value in values:
        row = ''.join(f'{str(v).rjust(width)} ' for v, width in zip(value, widths))
        rows.append(row)
    rows = "\n".join(rows)
    final_output = header + '\n' + rows
    return final_output

pattern = r"```sql\n([\s\S]*?)\n```"
def parse_sql(plain_result):
    # # TODO: move this somewhere else
    if type(plain_result) == str:
        sql_block = plain_result
    else:
        sql_block = 'SELECT' + plain_result['choices'][0]['text']
    
    SQL_PREFIX = "```sql\n"
    SQL_SUFFIX = "```"
    if (sql_block[:len(SQL_PREFIX)] == SQL_PREFIX) and (sql_block[-len(SQL_SUFFIX):] == SQL_SUFFIX):
        sql_block = sql_block[len(SQL_PREFIX):-len(SQL_SUFFIX)]
    elif '```' in sql_block:
        match = re.search(pattern, plain_result)
        if match:
            sql_block = match.group(1)
        else:
            sql_block = sql_block.replace('```sql\n', '```').replace('```SQL\n', '```')
            sql_block = sql_block.split('```', maxsplit=1)[-1]
            sql_block = sql_block.replace('```', '').strip()
    sql_block = sql_block.strip()
    if 'SELECT' != sql_block[:len('SELECT')]:
        sql_block = 'SELECT ' + sql_block
    return sql_block

def generate_schema_prompt(db_path, num_rows=None):
    # extract create ddls
    '''
    :param root_place:
    :param db_name:
    :return:
    '''
    full_schema_prompt_list = []
    with sqlite3.connect(db_path) as conn:
        # Create a cursor object
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        schemas = {}
        for table in tables:
            if table == 'sqlite_sequence':
                continue
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='{}';".format(table[0]))
            create_prompt = cursor.fetchone()[0]
            schemas[table[0]] = create_prompt
            if num_rows:
                cur_table = table[0]
                if cur_table in ['order', 'by', 'group']:
                    cur_table = "`{}`".format(cur_table)

                cursor.execute("SELECT * FROM {} LIMIT {}".format(cur_table, num_rows))
                column_names = [description[0] for description in cursor.description]
                values = cursor.fetchall()
                rows_prompt = nice_look_table(column_names=column_names, values=values)
                verbose_prompt = "/* \n {} example rows: \n SELECT * FROM {} LIMIT {}; \n {} \n */".format(num_rows, cur_table, num_rows, rows_prompt)
                schemas[table[0]] = "{} \n {}".format(create_prompt, verbose_prompt)

    for v in schemas.values():
        full_schema_prompt_list.append(v)

    schema_prompt = "\n\n".join(full_schema_prompt_list)

    return schema_prompt

def generate_comment_prompt(question, knowledge=None):
    pattern_prompt_no_kg = "-- Using valid SQLite, answer the following questions for the tables provided above."
    pattern_prompt_kg = "-- Using valid SQLite and understading External Knowledge, answer the following questions for the tables provided above."
    # question_prompt = "-- {}".format(question) + '\n SELECT '
    question_prompt = "-- Question: {}".format(question)

    if knowledge is None:
        result_prompt = pattern_prompt_no_kg + '\n' + question_prompt
    else:
        knowledge_prompt = "-- External Knowledge: {}".format(knowledge)
        result_prompt = knowledge_prompt + '\n' + pattern_prompt_kg + '\n' + question_prompt

    return result_prompt

def cot_wizard():
    cot = "\nGenerate the SQL after thinking step by step: "
    return cot
