def extract_json_string(res: str) -> str:
    """Extract the first valid json string from the response string (of LLMs).
    
    Return '' (empty string) if not found. Raise ValueError if an } is found before any {.
    """
    start, end = -1, -1
    cnt = 0  # act as a representation of a stack of '{' '}' pairs
    for i in range(len(res)):
        ch = res[i]
        if ch == '{':
            if cnt == 0:  # the first time '{' is encountered
                start = i
            cnt += 1
        elif ch == '}':
            if cnt <= 0:
                raise ValueError("found } before any { appears")
            cnt -= 1
            if cnt == 0:  # found the end index
                end = i
                break
    return res[start:end+1]

def strip_all_lines(s: str) -> str:
    """Remove all leading and trailing spaces of each line in the string."""
    return '\n'.join([line.strip() for line in s.splitlines()])
