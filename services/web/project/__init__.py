import os
import sqlalchemy
import bleach
import datetime
from flask import (
    Flask,
    jsonify,
    send_from_directory,
    request,
    make_response,
    redirect,
    render_template
)
from werkzeug.utils import secure_filename

app = Flask(__name__)

engine = sqlalchemy.create_engine(os.getenv('DATABASE_URL'), connect_args={'application_name': '__init__py'})
connection = engine.connect()


def make_cookie(username, password):
    response = make_response(redirect('/'))
    response.set_cookie('username', username)
    response.set_cookie('password', password)
    return response


def debug_info():
    print("request.args.get('username')=", request.args.get('username'))
    print("request.args.get('password')=", request.args.get('password'))

    print("request.form.get('username')=", request.form.get('username'))
    print("request.form.get('password')=", request.form.get('password'))

    print("request.cookies.get('username')=", request.cookies.get('username'))
    print("request.cookies.get('password')=", request.cookies.get('password'))


def credential_check(username, password):
    sql = sqlalchemy.sql.text("""
            SELECT id FROM users WHERE username = :username AND password = :password;""")
    res = connection.execute(sql, {
        'username': username,
        'password': password})
    if res.fetchone() is None:
        return False
    else:
        return True


def get_messages(a):
    messages = []
    sql = sqlalchemy.sql.text("""
        SELECT sender_id,
        message,
        created_at,
        id
        FROM messages ORDER BY created_at DESC LIMIT 20 OFFSET :offset;""")
    res = connection.execute(sql, {'offset': (a - 1) * 20})

    for row_messages in res.fetchall():
        sql = sqlalchemy.sql.text("""
                SELECT id,
                username,
                password,
                age
                FROM users WHERE id=:id;""")
        user_res = connection.execute(sql, {'id': row_messages[0]})
        row_users = user_res.fetchone()
        message = row_messages[1]
        cleaned_message = bleach.clean(message)
        linked_message = bleach.linkify(cleaned_message)
        messages.append({
            'id': row_messages[3],
            'message': linked_message,
            'username': row_users[1],
            'age': row_users[3],
            'created_at': row_messages[2]})
    return messages


def query_messages(query, a):
    sql = sqlalchemy.sql.text("""
        SELECT sender_id,
        ts_headline(
            message, to_tsquery(:query),
            'StartSel = "<mark><b>",
            StopSel = "</b></mark>"')
        AS highlighted_message,
        created_at,
        messages.id,
        username,
        age
        FROM messages JOIN users ON (messages.sender_id = users.id)
        WHERE to_tsvector('english', message) @@ to_tsquery(:query)
        ORDER BY to_tsvectory(message) <=> to_tsquery(:query),
        created_at DESC LIMIT 20 OFFSET :offset;""")

    res = connection.execute(sql, {
        'offset': 20 * (a - 1),
        'query': ' & '.join(query.split())
    })

    messages = []
    for row_messages in res.fetchall():
        message = row_messages[1]
        cleaned_message = bleach.clean(message, tags=['b', 'mark'])
        linked_message = bleach.linkify(cleaned_message)
        messages.append({
            'id': row_messages[3],
            'message': linked_message,
            'username': row_messages[4],
            'age': row_messages[5],
            'created_at': row_messages[2]})
    return messages


@app.route('/')
def root():
    debug_info()
    username = request.cookies.get('username')
    password = request.cookies.get('password')
    good_credentials = credential_check(username, password)
    print('good_credentials', good_credentials)
    try:
        page_number = int(request.args.get('page', 1))
    except TypeError:
        page_number = 1
    messages = get_messages(page_number)
    next_page = page_numer + 1
    prev_page = max(1, page_numer - 1)
    return render_template('root.html', messages=messages, good_credentials=good_credentials, username=username, page_number=page_number, next_page=next_page, prev_page=prev_page)


@app.route('/login', methods=['GET', 'POST'])
def login():
    debug_info()

    username = request.cookies.get('username')
    password = request.cookies.get('password')

    good_credentials = credential_check(username, password)
    print('good_credentials', good_credentials)
    if good_credentials:
        return redirect('/')

    username = request.form.get('username')
    password = request.form.get('password')

    good_credentials = credential_check(username, password)
    print('good_credentials', good_credentials)

    if password is None and username is None:
        return render_template('login.html')

    if username is None:
        return render_template('login.html', bad_credentials=False)
    else:
        if not good_credentials:
            return render_template('login.html', bad_credentials=True)
        else:
            return make_cookie(username, password)


@app.route('/logout')
def logout():
    debug_info()
    response = make_response(render_template('logout.html'))
    response.delete_cookie('username')
    response.delete_cookie('password')
    return response


@app.route('/create_account', methods=['GET', 'POST'])
def create_account():
    debug_info()

    username = request.cookies.get('username')
    password = request.cookies.get('password')

    good_credentials = credential_check(username, password)
    print("good_credentials = ", good_credentials)

    if good_credentials:
        return redirect('/')

    username_new = request.form.get('username_new')
    password_new = request.form.get('password_new')
    password_new2 = request.form.get('password_new2')
    age_new = request.form.get('new_age')

    if username_new is None:
        return render_template('create_user.html')

    elif not username_new or not password_new:
        return render_template('create_user.html', one_blank=True)

    elif not age_new.isnumeric():
        return render_template('create_user.html', invalid_age=True)

    else:
        if password_new != password_new2:
            return render_template('create_user.html', password_mismatch=True)
        else:
            try:
                sql = sqlalchemy.sql.text("""INSERT into users (username, password, age) values(:username, :password, :age);
                        """)

                res = connection.execute(sql, {
                    'username': username_new,
                    'password': password_new,
                    'age': age_new})
                print(res)
                return make_cookie(username_new, password_new)
            except sqlalchemy.exc.IntegrityError:
                return render_template('create_user.html', already_exists=True)


@app.route('/create_message', methods=['GET', 'POST'])
def create_message():
    username = request.cookies.get('username')
    password = request.cookies.get('password')
    good_credentials = credential_check(username, password)
    if not good_credentials:
        return redirect('/')

    sql = sqlalchemy.sql.text('''SELECT id FROM users
                                 WHERE username = :username AND password = :password''')

    res = connection.execute(sql, {
        'username': username,
        'password': password})

    for row in res.fetchall():
        sender_id = row[0]

    message = request.form.get('message')

    if message is None:
        return render_template('create_message.html', logged_in=good_credentials)
    elif not message:
        return render_template('create_message.html', invalid_message=True, logged_in=good_credentials)
    else:
        created_at = str(datetime.datetime.now()).split('.')[0]
        sql = sqlalchemy.sql.text("""
        INSERT INTO messages (sender_id,message,created_at) VALUES (:sender_id, :message, :created_at);
        """)
        res = connection.execute(sql, {
            'sender_id': sender_id,
            'message': message,
            'created_at': created_at})
    print(res)

    return render_template('create_message.html', logged_in=good_credentials, message_posted=True)


@app.route('/delete_message', methods=['GET', 'POST'])
def delete_message():
    message_id = request.form.get('message_id')

    sql = sqlalchemy.sql.text("""
        DELETE FROM messages WHERE id = :id;
        """)

    res = connection.execute(sql, {
        'id': message_id})
    print(res)
    return redirect('/')


@app.route('/search', methods=['GET', 'POST'])
def search():
    debug_info()
    username = request.cookies.get('username')
    password = request.cookies.get('password')
    good_credentials = credential_check(username, password)
    try:
        page_number = int(request.args.get('page', 1))
    except TypeError:
        page_number = 1
    next_page = page_number + 1
    prev_page = max(1, page_number - 1)
    if request.form.get('query'):
        query = request.form.get('query')
    else:
        query = request.args.get('query', '')
    if query:
        messages = query_messages(query, page_number)
    else:
        messages = get_messages(page_number)
    response = make_response(render_template('search.html', messages=messages, logged_in=good_credentials, username=username, page_number=page_number, next_page=next_page, prev_page=prev_page, query=query))
    if query:
        response.set_cookie('query', query)

    return response
