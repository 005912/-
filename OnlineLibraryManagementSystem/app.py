from flask import Flask, request, jsonify, render_template, session, redirect
from flask_bcrypt import Bcrypt
import mysql.connector
from flask_cors import CORS

app = Flask(__name__)
app.secret_key = "supersecretkey"  # session用
bcrypt = Bcrypt(app)
CORS(app)

# 数据库配置
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '你的密码',
    'database': 'book_db'
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

# 首页
@app.route('/')
def index():
    return render_template('index.html')

# 用户注册
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    hashed = bcrypt.generate_password_hash(password).decode('utf-8')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed))
        conn.commit()
    except mysql.connector.IntegrityError:
        cursor.close()
        conn.close()
        return jsonify({"message": "用户名已存在"}), 400
    cursor.close()
    conn.close()
    return jsonify({"message": "注册成功"}), 201

# 用户登录
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if user and bcrypt.check_password_hash(user['password'], password):
        session['user'] = {'id': user['id'], 'username': user['username'], 'role': user['role']}
        return jsonify({"message": "登录成功", "role": user['role']})
    return jsonify({"message": "用户名或密码错误"}), 401

# 用户登出
@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return jsonify({"message": "已登出"})

# 获取所有图书
@app.route('/books', methods=['GET'])
def get_books():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM books")
    books = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(books)

# 添加图书（管理员权限）
@app.route('/books', methods=['POST'])
def add_book():
    if 'user' not in session or session['user']['role'] != 'admin':
        return jsonify({'message': '权限不足'}), 403
    
    data = request.json
    title = data.get('title')
    author = data.get('author')
    year = data.get('published_year')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO books (title, author, published_year) VALUES (%s, %s, %s)",
                   (title, author, year))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'message': '图书添加成功！'}), 201

# 删除图书（管理员权限）
@app.route('/books/<int:book_id>', methods=['DELETE'])
def delete_book(book_id):
    if 'user' not in session or session['user']['role'] != 'admin':
        return jsonify({'message': '权限不足'}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM books WHERE id = %s", (book_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'message': '图书删除成功！'})

if __name__ == '__main__':
    app.run(debug=True)