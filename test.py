import os
import config_loader

file_name = r'./script.txt'
content_to_write = '第一段测试程序'

# 1. 检查文件是否存在
if os.path.exists(file_name):
    print(f"✅ 确认：当前目录下已存在 {file_name}")

    # (可选) 读取文件内容确认
    # logging.info(f"從 {config_path} 載入設定...")
    params = config_loader.load_and_validate_config(file_name)
else:
    print("没找到")


print("-" * 30)