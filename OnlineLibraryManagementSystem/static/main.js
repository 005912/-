let role = null;
let allBooks = [];

// 注册
async function register() {
    const username = document.getElementById('reg-username').value.trim();
    const password = document.getElementById('reg-password').value.trim();
    const msg = document.getElementById('auth-message');

    if(!username || !password){
        msg.textContent = '用户名和密码不能为空';
        msg.className = 'message error';
        return;
    }

    const res = await fetch('/register', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({username, password})
    });
    const data = await res.json();
    msg.textContent = data.message;
    msg.className = res.status===201?'message':'message error';
}

// 登录
async function login() {
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value.trim();
    const msg = document.getElementById('auth-message');

    if(!username || !password){
        msg.textContent = '用户名和密码不能为空';
        msg.className = 'message error';
        return;
    }

    const res = await fetch('/login', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({username, password})
    });
    const data = await res.json();
    if(res.status === 200){
        role = data.role;
        document.getElementById('auth-section').classList.add('hidden');
        document.getElementById('book-section').classList.remove('hidden');
        if(role !== 'admin'){
            document.getElementById('add-book-form').classList.add('hidden');
        }
        msg.textContent = '';
        fetchBooks();
    } else {
        msg.textContent = data.message;
        msg.className = 'message error';
    }
}

// 登出
async function logout(){
    await fetch('/logout', {method:'POST'});
    role = null;
    document.getElementById('auth-section').classList.remove('hidden');
    document.getElementById('book-section').classList.add('hidden');
}

// 获取图书
async function fetchBooks(){
    const res = await fetch('/books');
    allBooks = await res.json();
    displayBooks(allBooks);
}

// 展示图书
function displayBooks(books){
    const list = document.getElementById('book-list');
    list.innerHTML = '';
    books.forEach(book => {
        const li = document.createElement('li');
        li.textContent = `${book.title} - ${book.author} (${book.published_year})`;
        if(role==='admin'){
            const delBtn = document.createElement('button');
            delBtn.textContent = '删除';
            delBtn.onclick = ()=> deleteBook(book.id);
            li.appendChild(delBtn);
        }
        list.appendChild(li);
    });
}

// 搜索过滤
function filterBooks(){
    const keyword = document.getElementById('search').value.trim().toLowerCase();
    const filtered = allBooks.filter(b=>b.title.toLowerCase().includes(keyword)||b.author.toLowerCase().includes(keyword));
    displayBooks(filtered);
}

// 添加图书
async function addBook(){
    const title = document.getElementById('title').value.trim();
    const author = document.getElementById('author').value.trim();
    const year = parseInt(document.getElementById('year').value.trim());
    const msg = document.getElementById('book-message');

    if(!title || !author || !year){
        msg.textContent = '请完整填写信息';
        msg.className = 'message error';
        return;
    }

    const res = await fetch('/books',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({title, author, published_year: year})
    });
    const data = await res.json();
    msg.textContent = data.message;
    msg.className = res.status===201?'message':'message error';
    if(res.status===201){
        document.getElementById('title').value='';
        document.getElementById('author').value='';
        document.getElementById('year').value='';
        fetchBooks();
    }
}

// 删除图书
async function deleteBook(id){
    const res = await fetch(`/books/${id}`, {method:'DELETE'});
    const data = await res.json();
    alert(data.message);
    fetchBooks();
}