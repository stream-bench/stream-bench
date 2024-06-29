import sys
import sqlite3
from func_timeout import func_timeout, FunctionTimedOut

def execute_sql(predicted_sql, ground_truth, db_path, show_num_rows=10):
    conn = sqlite3.connect(db_path)
    # Connect to the database
    cursor = conn.cursor()
    cursor.execute(predicted_sql)
    predicted_res = cursor.fetchall()
    pred_md_table = "| " + " | ".join(["Column{}".format(i + 1) for i in range(len(predicted_res[0]))]) + " |\n"
    pred_md_table += "| " + " | ".join(["---" for _ in range(len(predicted_res[0]))]) + " |\n"
    for row in predicted_res[:show_num_rows]:
        pred_md_table += "| " + " | ".join(map(str, row)) + " |\n"
    cursor.execute(ground_truth)
    ground_truth_res = cursor.fetchall()

    gt_md_table = "| " + " | ".join(["Column{}".format(i + 1) for i in range(len(ground_truth_res[0]))]) + " |\n"
    gt_md_table += "| " + " | ".join(["---" for _ in range(len(ground_truth_res[0]))]) + " |\n"
    for row in ground_truth_res[:show_num_rows]:
        gt_md_table += "| " + " | ".join(map(str, row)) + " |\n"
    res = 0
    if set(predicted_res) == set(ground_truth_res):
        res = 1
    return res, pred_md_table, gt_md_table

def execute_model(predicted_sql, ground_truth, db_path, meta_time_out=30):
    pred_md_table, gt_md_table = '', ''
    try:
        res, pred_md_table, gt_md_table = func_timeout(meta_time_out, execute_sql,
                            args=(predicted_sql, ground_truth, db_path)
                        )
        result = pred_md_table
    except KeyboardInterrupt:
        sys.exit(0)
    except FunctionTimedOut:
        result = 'Database execution timeout'
        res = 0
    except Exception as e:
        result = str(e)
        res = 0
    return res, (result, gt_md_table)
