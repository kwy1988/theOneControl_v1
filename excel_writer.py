# excel_writer.py
import pandas as pd
import numpy as np
import logging

def write_to_excel(all_cycles_data, output_path, params):
    """
    將多個循環的數據寫入單一 Excel 檔案的不同工作表中。

    Args:
        all_cycles_data (dict): 字典，鍵是工作表名稱 (str)，值是 DataFrame。
        output_path (str): 輸出的 Excel 檔案路徑。
    """
    try:
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            for sheet_name, df in all_cycles_data.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                logging.info(f"成功將數據寫入到工作表: '{sheet_name}'")
            config_df = pd.DataFrame(list(params.items()), columns=['Parameter', 'Value'])
            config_df.to_excel(writer, sheet_name='Config', index=False)

        logging.info(f"成功將所有數據寫入到: {output_path}")
    except Exception as e:
        logging.error(f"寫入 Excel 失敗: {e}")
        raise