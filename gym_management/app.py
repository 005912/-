import os
import argparse
import logging
import socket
import traceback
from flask import Flask, session, jsonify, request, render_template, flash, redirect, url_for
import pymysql
from datetime import datetime, timedelta
from config import DevelopmentConfig
from werkzeug.security import check_password_hash, generate_password_hash

# 彻底禁用可能导致编码问题的反向DNS查询
def disable_reverse_dns():
    """禁用反向DNS查询，避免编码错误"""
    original_gethostbyaddr = socket.gethostbyaddr

    def safe_gethostbyaddr(ip):
        """完全避免DNS查询，直接返回IP"""
        return ip, [], [ip]

    # 替换原函数
    socket.gethostbyaddr = safe_gethostbyaddr

# 在应用启动前禁用反向DNS查询
disable_reverse_dns()

# 配置日志 - 简化版本，避免任何可能的编码问题
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# 只初始化一次Flask应用
app = Flask(__name__)
app.config.from_object(DevelopmentConfig)
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key_here')  # 优先使用环境变量
app.permanent_session_lifetime = timedelta(hours=2)  # 设置会话过期时间

def get_db_connection():
    """创建数据库连接"""
    try:
        return pymysql.connect(
            host=app.config['DB_HOST'],
            user=app.config['DB_USER'],
            password=app.config['DB_PASSWORD'],
            database=app.config['DB_NAME'],
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
    except Exception as e:
        logging.error(f"数据库连接失败: {e}")
        raise  # 抛出异常让调用者处理

# 数据库查询执行函数
def execute_query(query, params=()):
    """执行数据库查询"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
    except Exception as e:
        logging.error(f"数据库查询失败: {e}，查询: {query}，参数: {params}")
        return None
    finally:
        conn.close()

# ========== 首页和仪表盘 ==========

@app.route('/')#当用户访问网站根目录时，请调用下面的 index 函数来处理这个请求#Flask 的路由装饰器，用于将一个 URL 路径与一个 Python 函数（视图函数）绑定。
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
#未登录返回login页面
    # 初始化默认数据
    today_reservations = 0
    total_checkins = 0
    current_reservations = []

    try:
        # 统计今日预约数
        today_reservations_result = execute_query("""
            SELECT COUNT(*) as today_reservations 
            FROM Reservation 
            WHERE user_id = %s AND DATE(created_time) = CURDATE() AND status = '已预约'
        """, (session['user_id'],))

        if today_reservations_result and len(today_reservations_result) > 0:
            today_reservations = today_reservations_result[0]['today_reservations']

        # 统计总打卡次数
        total_checkins_result = execute_query("""
            SELECT COUNT(*) as total_checkins 
            FROM FitnessCheckIn 
            WHERE user_id = %s
        """, (session['user_id'],))

        if total_checkins_result and len(total_checkins_result) > 0:
            total_checkins = total_checkins_result[0]['total_checkins']

        # 获取当前有效预约
        current_reservations_result = execute_query("""
            SELECT r.reservation_id, g.date, g.time_slot
            FROM Reservation r
            JOIN GymTimeslot g ON r.slot_id = g.slot_id
            WHERE r.user_id = %s AND r.status = '已预约' AND g.date >= CURDATE()
            ORDER BY g.date, g.time_slot
            LIMIT 5
        """, (session['user_id'],))

        current_reservations = current_reservations_result if current_reservations_result else []
    except Exception as e:
        logging.error(f"仪表盘数据查询失败: {e}")
        flash('获取仪表盘数据时发生错误', 'error')

    return render_template('dashboard.html',
                           user_name=session.get('user_name', '用户'),
                           today_reservations=today_reservations,
                           total_checkins=total_checkins,
                           current_reservations=current_reservations)
    #数据接入到bashboard.html

# ========== 用户认证接口 ==========

@app.route('/register', methods=['GET', 'POST'])#get请求和post请求
def register():
    if request.method == 'POST':
        # 从表单获取数据
        student_no = request.form.get('student_no')
        name = request.form.get('name')
        college = request.form.get('college')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # 1. 验证必填字段
        if not all([student_no, name, college, password, confirm_password]):
            flash('请填写所有必填字段', 'error')
            return render_template('auth/register.html')

        # 2. 验证两次密码输入一致
        if password != confirm_password:
            flash('两次输入的密码不一致', 'error')
            return render_template('auth/register.html')

        # 3. 密码哈希化
        hashed_password = generate_password_hash(password)

        conn = None
        try:
            # 4. 获取数据库连接
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # 5. 检查学号是否已存在
                cursor.execute("SELECT user_id FROM user WHERE student_no = %s", (student_no,))
                if cursor.fetchone():
                    flash('该学号已注册', 'error')
                    return render_template('auth/register.html')

                # 6. 插入新用户
                sql = """INSERT INTO user (student_no, name, college, password) 
                         VALUES (%s, %s, %s, %s)"""
                cursor.execute(sql, (student_no, name, college, hashed_password))

                # 7. 提交事务
                conn.commit()

            # 8. 注册成功，重定向到登录页
            flash('注册成功，请登录', 'success')
            return redirect(url_for('login'))

        except Exception as e:
            # 9. 处理异常，回滚事务
            if conn:
                conn.rollback()
            logging.error(f"注册失败: {e}")
            flash('注册失败，请稍后重试。', 'error')
            return render_template('auth/register.html')
        finally:
            # 10. 确保数据库连接被关闭
            if conn:
                conn.close()

    # 11. GET 请求，显示注册表单
    return render_template('auth/register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        student_no = request.form.get('student_no')
        password = request.form.get('password')

        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT user_id, student_no, name, college, password FROM User WHERE student_no = %s",
                    (student_no,))
                user_data = cursor.fetchone()

                if user_data and check_password_hash(user_data['password'], password):
                    # 设置会话信息
                    session['user_id'] = user_data['user_id']
                    session['student_no'] = user_data['student_no']
                    session['user_name'] = user_data['name']
                    session['college'] = user_data['college']
                    session['logged_in'] = True

                    flash('登录成功', 'success')
                    logging.info(f"用户 {user_data['name']} 登录成功")
                    return redirect(url_for('dashboard'))
                else:
                    flash('学号或密码错误', 'error')

        except Exception as e:
            logging.error(f'登录数据库操作失败: {e}')
            flash('登录失败，请稍后重试', 'error')
        finally:
            if conn:
                conn.close()

    return render_template('auth/login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('已退出登录', 'success')
    return redirect(url_for('index'))


# ========== 时段管理接口 ==========

@app.route('/slots')#实现健身房时段管理和预约查看
def view_slots():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        date_str = request.args.get('date')
        if not date_str:
            date_str = datetime.now().strftime('%Y-%m-%d')

        slots_result = execute_query("""
            SELECT slot_id, date, time_slot, total_capacity, remaining_capacity 
            FROM GymTimeslot 
            WHERE date = %s 
            ORDER BY time_slot
        """, (date_str,))

        slots = slots_result if slots_result else []

        # 检查用户是否已预约各时段
        for slot in slots:
            reservation_result = execute_query("""
                SELECT reservation_id FROM Reservation 
                WHERE user_id = %s AND slot_id = %s AND status = '已预约'
            """, (session['user_id'], slot['slot_id']))
            slot['user_has_reserved'] = bool(reservation_result)

        # 获取未来7天的日期
        dates = []
        for i in range(7):
            day = datetime.now() + timedelta(days=i)
            dates.append({
                'date': day.strftime('%Y-%m-%d'),
                'display': day.strftime('%m/%d')
            })

        return render_template('slots/list.html', slots=slots, selected_date=date_str, dates=dates)

    except Exception as e:
        logging.error(f"查看时段页面错误: {e}")
        flash('加载时段信息失败，请稍后重试', 'error')
        return redirect(url_for('dashboard'))


# ========== 预约管理接口 ==========

@app.route('/reserve/<int:slot_id>', methods=['POST'])
def reserve_slot(slot_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '请先登录'})

    # 检查是否已经预约
    existing_reservation = execute_query("""
        SELECT reservation_id FROM Reservation 
        WHERE user_id = %s AND slot_id = %s AND status = '已预约'
    """, (session['user_id'], slot_id))

    if existing_reservation:
        return jsonify({'success': False, 'message': '您已经预约了该时段'})

    # 检查时段是否还有剩余名额
    slot_info = execute_query("SELECT remaining_capacity FROM GymTimeslot WHERE slot_id = %s", (slot_id,))
    if not slot_info or slot_info[0]['remaining_capacity'] <= 0:
        return jsonify({'success': False, 'message': '该时段已满，无法预约'})

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 创建预约记录
            cursor.execute("""
                INSERT INTO Reservation (user_id, slot_id, status) 
                VALUES (%s, %s, '已预约')
            """, (session['user_id'], slot_id))

            # 更新剩余名额
            cursor.execute("""
                UPDATE GymTimeslot 
                SET remaining_capacity = remaining_capacity - 1 
                WHERE slot_id = %s
            """, (slot_id,))

            conn.commit()
            return jsonify({'success': True, 'message': '预约成功'})

    except Exception as e:
        logging.error(f"预约失败: {e}")
        return jsonify({'success': False, 'message': '预约失败'})
    finally:
        if conn:
            conn.close()


# ========== 健身打卡接口 ==========

@app.route('/checkin_form')
def checkin_form():
    """健身打卡页面"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        user_id = session['user_id']
        today = datetime.now().date()
        user_name = session.get('user_name', '用户')

        logging.info(f"用户 {user_id}({user_name}) 访问打卡页面")

        # 查询用户今日的有效预约
        reservations = execute_query("""
            SELECT 
                r.reservation_id, 
                r.status, 
                r.created_time,
                g.date, 
                g.time_slot, 
                g.total_capacity, 
                g.remaining_capacity
            FROM Reservation r
            JOIN GymTimeslot g ON r.slot_id = g.slot_id
            WHERE r.user_id = %s 
            AND g.date = %s 
            AND r.status = '已预约'
            ORDER BY g.time_slot
        """, (user_id, today))

        reservations = reservations if reservations else []
        logging.info(f"用户 {user_id} 今日预约数量: {len(reservations)}")

        return render_template('checkins/checkin_form.html',
                               reservations=reservations,
                               today=today,
                               user_name=user_name)

    except Exception as e:
        logging.error(f"获取打卡数据失败: {e}")
        logging.error(f"错误堆栈: {traceback.format_exc()}")
        flash('加载打卡页面失败', 'error')
        return render_template('checkins/checkin_form.html',
                               reservations=[],
                               today=datetime.now().date())


@app.route('/checkin', methods=['POST'])
def checkin():
    """提交健身打卡"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '请先登录'})

    try:
        reservation_id = request.form.get('reservation_id')
        actual_duration = request.form.get('actual_duration')
        user_id = session['user_id']

        if not reservation_id or not actual_duration:
            return jsonify({'success': False, 'message': '请填写完整信息'})

        # 验证预约是否属于当前用户且是今日的有效预约
        reservation = execute_query("""
            SELECT r.reservation_id, g.date
            FROM Reservation r
            JOIN GymTimeslot g ON r.slot_id = g.slot_id
            WHERE r.reservation_id = %s 
            AND r.user_id = %s 
            AND r.status = '已预约'
            AND g.date = CURDATE()
        """, (reservation_id, user_id))

        if not reservation:
            return jsonify({'success': False, 'message': '无效的预约或预约不属于今日'})

        # 检查是否已经打卡过
        existing_checkin = execute_query("""
            SELECT checkin_id FROM FitnessCheckIn 
            WHERE reservation_id = %s
        """, (reservation_id,))

        if existing_checkin:
            return jsonify({'success': False, 'message': '该时段已经打卡过了'})

        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # 插入打卡记录
                cursor.execute("""
                    INSERT INTO FitnessCheckIn (user_id, reservation_id, actual_duration, checkin_time)
                    VALUES (%s, %s, %s, NOW())
                """, (user_id, reservation_id, actual_duration))

                conn.commit()
                return jsonify({'success': True, 'message': '打卡成功'})

        except Exception as e:
            logging.error(f"打卡失败: {e}")
            return jsonify({'success': False, 'message': '打卡失败'})
        finally:
            if conn:
                conn.close()

    except Exception as e:
        logging.error(f"打卡处理失败: {e}")
        return jsonify({'success': False, 'message': '系统错误'})


@app.route('/my_checkins')
def my_checkins():
    """我的打卡记录"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        user_id = session['user_id']

        # 查询用户的打卡记录
        checkins = execute_query("""
            SELECT 
                c.checkin_id,
                c.actual_duration,
                c.checkin_time,
                g.date,
                g.time_slot,
                r.reservation_id
            FROM FitnessCheckIn c
            JOIN Reservation r ON c.reservation_id = r.reservation_id
            JOIN GymTimeslot g ON r.slot_id = g.slot_id
            WHERE c.user_id = %s
            ORDER BY c.checkin_time DESC
        """, (user_id,))

        checkins = checkins if checkins else []

        # 计算统计信息
        total_checkins = len(checkins)
        total_duration = sum(float(checkin['actual_duration']) for checkin in checkins) if checkins else 0
        average_duration = total_duration / total_checkins if total_checkins > 0 else 0
        efficient_training_count = sum(1 for checkin in checkins if float(checkin['actual_duration']) >= 1.5) if checkins else 0

        return render_template('checkins/my_checkins.html',
                              checkins=checkins,
                              total_checkins=total_checkins,
                              total_duration=total_duration,
                              average_duration=average_duration,
                              efficient_training_count=efficient_training_count)

    except Exception as e:
        logging.error(f"获取打卡记录失败: {e}")
        flash('加载打卡记录失败', 'error')
        return render_template('checkins/my_checkins.html',
                              checkins=[],
                              total_checkins=0,
                              total_duration=0,
                              average_duration=0,
                              efficient_training_count=0)


# ========== 预约记录接口 ==========

@app.route('/my_reservations')
def my_reservations():
    """我的预约记录"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        user_id = session['user_id']
        user_name = session.get('user_name', '用户')

        logging.info(f"用户 {user_id}({user_name}) 访问我的预约")

        # 获取用户的预约记录
        reservations = execute_query("""
            SELECT r.reservation_id, r.status, r.created_time,
                   g.date, g.time_slot, g.total_capacity, g.remaining_capacity
            FROM Reservation r
            JOIN GymTimeslot g ON r.slot_id = g.slot_id
            WHERE r.user_id = %s
            ORDER BY g.date DESC, g.time_slot DESC
        """, (user_id,))

        reservations = reservations if reservations else []
        logging.info(f"用户 {user_id} 预约记录数量: {len(reservations)}")

        return render_template('reservations/my_reservations.html',
                               reservations=reservations)

    except Exception as e:
        logging.error(f"获取预约记录失败: {e}")
        flash('加载预约记录失败', 'error')
        return render_template('reservations/my_reservations.html', reservations=[])


@app.route('/cancel_reservation/<int:reservation_id>', methods=['POST'])
def cancel_reservation(reservation_id):
    """取消预约"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '请先登录'})

    logging.info(f"用户 {session['user_id']} 尝试取消预约 {reservation_id}")

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 检查预约是否存在且属于当前用户
            cursor.execute("""
                SELECT r.slot_id, r.status FROM Reservation r 
                WHERE r.reservation_id = %s AND r.user_id = %s
            """, (reservation_id, session['user_id']))

            reservation = cursor.fetchone()
            logging.info(f"查询到的预约: {reservation}")

            if not reservation:
                return jsonify({'success': False, 'message': '预约不存在或无法取消'})

            if reservation['status'] != '已预约':
                return jsonify({'success': False, 'message': '该预约无法取消'})

            # 更新预约状态为已取消
            cursor.execute("""
                UPDATE Reservation SET status = '已取消' 
                WHERE reservation_id = %s
            """, (reservation_id,))

            # 恢复时段容量
            cursor.execute("""
                UPDATE GymTimeslot 
                SET remaining_capacity = remaining_capacity + 1 
                WHERE slot_id = %s
            """, (reservation['slot_id'],))

            conn.commit()
            logging.info(f"预约 {reservation_id} 取消成功")
            return jsonify({'success': True, 'message': '取消预约成功'})

    except Exception as e:
        logging.error(f"取消预约失败: {e}")
        return jsonify({'success': False, 'message': '取消预约失败'})
    finally:
        if conn:
            conn.close()


# ========== 初始化示例数据 ==========

@app.route('/init_sample_data')
def init_sample_data():
    """初始化示例数据（仅测试使用）"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # 仅在调试模式下允许使用
    if not app.debug:
        flash('该功能仅在调试模式下可用', 'error')
        return redirect(url_for('dashboard'))

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:

            # 清空现有数据
            cursor.execute("DELETE FROM FitnessCheckIn")
            cursor.execute("DELETE FROM Reservation")
            cursor.execute("DELETE FROM GymTimeslot")

            # 添加示例时段数据 - 未来7天，每天7个时段
            sample_slots = []
            time_slots = [
                '08:00-10:00',
                '10:00-12:00',
                '12:00-14:00',
                '14:00-16:00',
                '16:00-18:00',
                '18:00-20:00',
                '20:00-22:00'
            ]

            for i in range(7):  # 未来7天
                date = (datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d')

                for time_slot in time_slots:
                    # 每个时段容量设为20人
                    sample_slots.append((date, time_slot, 20, 20))

            cursor.executemany("""
                INSERT INTO GymTimeslot (date, time_slot, total_capacity, remaining_capacity) 
                VALUES (%s, %s, %s, %s)
            """, sample_slots)

            # 为当前用户创建今日的预约（用于测试）
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute("SELECT slot_id FROM GymTimeslot WHERE date = %s LIMIT 3", (today,))
            today_slots = cursor.fetchall()

            for slot in today_slots:
                cursor.execute("""
                    INSERT INTO Reservation (user_id, slot_id, status) 
                    VALUES (%s, %s, '已预约')
                """, (session['user_id'], slot['slot_id']))

                # 更新剩余容量
                cursor.execute("""
                    UPDATE GymTimeslot 
                    SET remaining_capacity = remaining_capacity - 1 
                    WHERE slot_id = %s
                """, (slot['slot_id'],))

            # 验证插入的数据
            cursor.execute("SELECT COUNT(*) as count FROM GymTimeslot")
            inserted_count = cursor.fetchone()

            conn.commit()
            flash(f'示例数据初始化成功！插入了 {inserted_count["count"]} 个时段记录，并为当前用户创建了3个今日预约。',
                  'success')

    except Exception as e:
        logging.error(f"初始化示例数据失败: {e}")
        flash(f'初始化示例数据失败: {str(e)}', 'error')
    finally:
        if conn:
            conn.close()

    return redirect(url_for('dashboard'))


# 全局错误处理
@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    logging.error(f"服务器内部错误: {e}")
    return render_template('errors/500.html'), 500


# 启动 Flask 应用
if __name__ == '__main__':
    # 配置选项（按优先级排序）：
    # 1. 命令行参数
    # 2. 环境变量
    # 3. 默认值

    parser = argparse.ArgumentParser(description='启动健身房预约系统')
    parser.add_argument('--port', type=int, default=None, help='服务端口号')
    parser.add_argument('--host', type=str, default=None, help='服务主机')
    parser.add_argument('--debug', action='store_true', help='调试模式')
    args = parser.parse_args()

    # 确定端口（命令行参数 > 环境变量 > 默认值）
    port = args.port
    if port is None:
        port = int(os.environ.get('PORT', 5000))

    # 确定主机
    host = args.host
    if host is None:
        host = os.environ.get('HOST', '127.0.0.1')

    # 确定调试模式
    #debug = args.debug if args.debug is not None else app.config.get('DEBUG', True)
    debug=True
    try:
        app.run(debug=debug, host=host, port=port)
    except Exception as e:
        logging.error(f"启动失败: {e}")
        print(f"错误: 端口 {port} 可能已被占用，请尝试其他端口")