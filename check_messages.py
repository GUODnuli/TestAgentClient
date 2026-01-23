import sqlite3

conn = sqlite3.connect('storage/tasks.db')
cursor = conn.cursor()

# 查看表结构
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("数据库中的表:")
for table in tables:
    print(f"  - {table[0]}")
    cursor.execute(f"PRAGMA table_info({table[0]})")
    columns = cursor.fetchall()
    for col in columns:
        print(f"      {col[1]} ({col[2]})")

# 查询最新的对话
cursor.execute('SELECT conversation_id, user_id, title FROM conversations ORDER BY created_at DESC LIMIT 1')
conv = cursor.fetchone()
if conv:
    print("\n最新对话:")
    print(f"  ID: {conv[0]}")
    print(f"  标题: {conv[2] or '(无标题)'}")
    
    # 查询该对话的消息
    cursor.execute('SELECT role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY created_at', (conv[0],))
    messages = cursor.fetchall()
    print(f"\n对话中的消息 ({len(messages)} 条):")
    for msg in messages:
        print(f"  [{msg[0]}] {msg[1][:100]}...")
        print(f"    时间: {msg[2]}")
else:
    print("\n没有找到对话")

conn.close()
