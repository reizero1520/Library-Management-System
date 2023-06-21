import sqlite3

def create_staff_table():
    conn = sqlite3.connect('staff.db', check_same_thread=False)
    cursor_staff = conn.cursor()

    cursor_staff.execute('''
        CREATE TABLE IF NOT EXISTS staff (
            staff_id TEXT NOT NULL PRIMARY KEY,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            firstname TEXT NOT NULL,
            lastname TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0
        )
    ''')
    conn.commit()


def create_members_table():
    # Connect to the registrants database
    conn = sqlite3.connect('members.db', check_same_thread=False)
    cursor_members = conn.cursor()

    # Create the registrants table if it doesn't exist
    cursor_members.execute('''
        CREATE TABLE IF NOT EXISTS members (
            member_id TEXT NOT NULL PRIMARY KEY,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            phone TEXT NOT NULL,
            birthday TEXT NOT NULL,
            firstname TEXT NOT NULL,
            lastname TEXT NOT NULL
        )
    ''')
    conn.commit()

def create_books_table():
    # Connect to the books database
    conn_books = sqlite3.connect('books.db', check_same_thread=False)
    cursor_books = conn_books.cursor()

    # Create the books table if it doesn't exist
    cursor_books.execute('''
        CREATE TABLE IF NOT EXISTS books (
            book_id TEXT NOT NULL,
            isbn TEXT NOT NULL,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            description TEXT NOT NULL,
            publisher TEXT NOT NULL,
            publication_date TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            PRIMARY KEY (book_id, isbn)
        )
    ''')
    conn_books.commit()

def create_borrowed_books_table():
    # Connect to the borrowed books database
    conn = sqlite3.connect('borrowed_books.db', check_same_thread=False)
    cursor = conn.cursor()

    # Create the borrowed_books table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS borrowed_books (
            borrow_id TEXT NOT NULL PRIMARY KEY,
            member_id TEXT NOT NULL,
            book_id TEXT NOT NULL,
            due_date TEXT NOT NULL,
            expected_return TEXT,
            date_borrowed TEXT,
            quantity INTEGER,
            penalty INTEGER,
            date_returned TEXT,
            FOREIGN KEY (member_id) REFERENCES members (member_id),
            FOREIGN KEY (book_id) REFERENCES books (book_id)
        )
    ''')
    conn.commit()

def create_borrowings_table():
    conn = sqlite3.connect('borrowings.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS borrowings (
            borrowing_id TEXT NOT NULL PRIMARY KEY,
            book_id TEXT NOT NULL,
            username TEXT,
            borrow_date TEXT,
            return_date TEXT,
            FOREIGN KEY (book_id) REFERENCES books (id),
            FOREIGN KEY (username) REFERENCES users (username)
        )
    ''')

    conn.commit()

def create_pending_borrowings_table():
     conn = sqlite3.connect('pending_borrowings.db', check_same_thread=False)
     cursor = conn.cursor()

     cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_borrowings (
            pending_id TEXT NOT NULL,
            member_id TEXT NOT NULL,
            book_id TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            FOREIGN KEY (member_id) REFERENCES members (member_id),
            FOREIGN KEY (book_id) REFERENCES books (book_id)
        )
    ''')

     conn.commit()


