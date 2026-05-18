import pymysql
from datetime import datetime, timedelta

# 数据库连接配置
config = {
    'host': 'localhost',
    'user': 'root',
    'password': '123456',  # 修改为你的密码
    'database': '健身预约平台',
    'charset': 'utf8mb4'
}


def init_gym_slots():
    """初始化健身房时段"""
    try:
        conn = pymysql.connect(**config)
        cursor = conn.cursor()

        # 清空现有数据
        cursor.execute("DELETE FROM GymTimeslot")

        # 时段配置
        time_slots = [
            '08:00-10:00',
            '10:00-12:00',
            '12:00-14:00',
            '14:00-16:00',
            '16:00-18:00',
            '18:00-20:00',
            '20:00-22:00'
        ]

        # 插入未来7天的数据
        slots_data = []
        for i in range(7):
            date = (datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d')
            for time_slot in time_slots:
                slots_data.append((date, time_slot, 20, 20))

        # 批量插入
        sql = """
        INSERT INTO GymTimeslot (date, time_slot, total_capacity, remaining_capacity) 
        VALUES (%s, %s, %s, %s)
        """
        cursor.executemany(sql, slots_data)

        conn.commit()
        print(f"✅ 成功插入 {len(slots_data)} 个时段记录")

        # 验证数据
        cursor.execute("SELECT COUNT(*) as count FROM GymTimeslot")
        count = cursor.fetchone()[0]
        cursor.execute("SELECT DISTINCT date FROM GymTimeslot ORDER BY date LIMIT 3")
        dates = cursor.fetchall()

        print(f"📊 总时段数: {count}")
        print("📅 可用日期:")
        for date in dates:
            print(f"  - {date[0]}")

    except Exception as e:
        print(f"❌ 初始化失败: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()


if __name__ == '__main__':
    print("🚀 开始初始化健身房时段...")
    init_gym_slots()