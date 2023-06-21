import sqlite3
import datetime
import uuid
import requests
import json
from flask import Flask, render_template, request, redirect, session, flash, jsonify
from database_setup import create_members_table, create_books_table, create_staff_table, create_borrowed_books_table, create_borrowings_table, create_pending_borrowings_table

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Create the tables if they don't exist
create_members_table()
create_books_table()
create_staff_table()
create_borrowed_books_table()
create_borrowings_table()
create_pending_borrowings_table()


def search_isbn(title):
    # Use the Open Library Search API to find the book by title
    url = f'https://openlibrary.org/search.json?q={title}'
    response = requests.get(url)
    data = response.json()

    if 'docs' in data and len(data['docs']) > 0:
        # Retrieve the first result and extract the ISBN
        first_result = data['docs'][0]
        if 'isbn' in first_result:
            return first_result['isbn'][0]

    return None

def calculate_due_date():
    current_date = datetime.date.today()
    due_date = current_date + datetime.timedelta(days=7)  # Adding 7 days as an example
    return due_date.strftime('%Y-%m-%d')  # Return the due date in the desired format

# Function to generate a unique borrow ID
def generate_unique_id():
    return str(uuid.uuid4())

def retrieve_book_by_id(book_id):
    conn = sqlite3.connect('books.db')
    cursor = conn.cursor()

    # Retrieve the book details based on the book ID
    cursor.execute('SELECT title, author FROM books WHERE book_id = ?', (book_id,))
    book = cursor.fetchone()

    conn.close()

    if book:
        return {
            'title': book[0],
            'author': book[1]
        }
    else:
        return None

# Function to update the quantity of a book in the database
def update_book_quantity(book_id, new_quantity):
    conn = sqlite3.connect('books.db')
    cursor = conn.cursor()

    # Execute an UPDATE query to update the book quantity
    cursor.execute("UPDATE books SET quantity=? WHERE book_id=?", (new_quantity, book_id))

    # Commit the changes to the database
    conn.commit()

    # Close the database connection
    conn.close()

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Retrieve the username and password from the login form
        username = request.form['username']
        password = request.form['password']

        # Connect to the staff database
        conn_staff = sqlite3.connect('staff.db', check_same_thread=False)
        cursor_staff = conn_staff.cursor()

        # Check if the username and password are valid in the staff database
        cursor_staff.execute("SELECT * FROM staff WHERE username = ? AND password = ?", (username, password))
        staff_user = cursor_staff.fetchone()

        if staff_user:
            # Fetch staff details from the retrieved row
            staff_id, _, email, _, firstname, lastname, is_admin = staff_user

            # Store staff details in session
            session['staff_id'] = staff_id
            session['username'] = username
            session['email'] = email
            session['firstname'] = firstname
            session['lastname'] = lastname
            session['is_admin'] = bool(is_admin)

            if is_admin:
                # Redirect to the admin dashboard
                return redirect('/admin/dashboard')
            else:
                # Redirect to the staff dashboard
                return redirect('/staff/dashboard')

        # Connect to the members database
        conn_members = sqlite3.connect('members.db', check_same_thread=False)
        cursor_members = conn_members.cursor()

        # Check if the username and password are valid in the members database
        cursor_members.execute("SELECT * FROM members WHERE username = ? AND password = ?", (username, password))
        member_user = cursor_members.fetchone()

        if member_user:
            # Fetch member details from the retrieved row
            member_id, _, email, _, phone, birthday, firstname, lastname = member_user

            # Store member details in session
            session['member_id'] = member_id
            session['username'] = username
            session['email'] = email
            session['phone'] = phone
            session['birthday'] = birthday
            session['firstname'] = firstname
            session['lastname'] = lastname
            

            # Redirect to the user dashboard
            return redirect('/user/dashboard')

        error_message = "Invalid username or password. Please try again."
        return render_template('login.html', error=error_message)

    else:
        return render_template('login.html')
    
@app.route('/user/dashboard')
def user_dashboard():
    # Check if the user is authenticated and not an admin
    if 'username' in session and not session.get('is_admin'):
        # Retrieve the list of available books from the database
        conn_books = sqlite3.connect('books.db')
        cursor_books = conn_books.cursor()
        cursor_books.execute("SELECT * FROM books WHERE quantity > 0")
        available_books = cursor_books.fetchall()
        
        # Retrieve the borrowings data for the user
        conn_borrowings = sqlite3.connect('borrowings.db')
        cursor_borrowings = conn_borrowings.cursor()

        # Fetch the borrowings for the user
        cursor_borrowings.execute('SELECT * FROM borrowings WHERE username = ?', (session['username'],))
        borrowings = cursor_borrowings.fetchall()

        # Close the database connections
        cursor_books.close()
        conn_books.close()
        cursor_borrowings.close()
        conn_borrowings.close()

        # Pass the username, borrowings, and available books to the template
        return render_template('user_dashboard.html', username=session['username'], borrowings=borrowings, available_books=available_books)
    else:
        return redirect('/')

@app.route('/book_details')
def book_details():
    book_id = request.args.get('book_id')

    # Retrieve book details from the database based on the book ID
    conn_books = sqlite3.connect('books.db')
    cursor_books = conn_books.cursor()
    cursor_books.execute("SELECT * FROM books WHERE book_id = ?", (book_id,))
    book_details = cursor_books.fetchone()
    conn_books.close()

    if book_details:
        # Format the book details as a dictionary
        book = {
            'book_id': book_details[0],
            'isbn': book_details[1],
            'title': book_details[2],
            'author': book_details[3],
            'description': book_details[4],
            'publisher': book_details[5],
            'publication_date': book_details[6],
            'quantity': book_details[7]
        }
        return jsonify(book)
    else:
        return jsonify({'message': 'Book not found.'}), 404

@app.route('/add_to_borrowings', methods=['POST'])
def add_to_borrowings():
    data = request.get_json()
    book_id = data.get('book_id')
    title = data.get('title')
    quantity = int(data.get('quantity'))

    # Check if the user is authenticated and not an admin
    if 'username' in session and not session.get('is_admin'):
        # Retrieve the member ID of the user from the database
        conn_members = sqlite3.connect('members.db')
        cursor_members = conn_members.cursor()
        cursor_members.execute("SELECT member_id FROM members WHERE username = ?", (session['username'],))
        member_id = cursor_members.fetchone()[0]

        # Generate a UUID for the pending borrowing entry
        pending_id = str(uuid.uuid4())

        # Insert the borrowing details into the pending_borrowings table
        conn_pending_borrowings = sqlite3.connect('pending_borrowings.db')
        cursor_pending_borrowings = conn_pending_borrowings.cursor()
        cursor_pending_borrowings.execute("""
            INSERT INTO pending_borrowings (pending_id, member_id, book_id, quantity)
            VALUES (?, ?, ?, ?)
        """, (pending_id, member_id, book_id, quantity))
        conn_pending_borrowings.commit()

        # Retrieve the book title and author from the books database
        conn_books = sqlite3.connect('books.db')
        cursor_books = conn_books.cursor()
        cursor_books.execute("SELECT title, author FROM books WHERE book_id = ?", (book_id,))
        book_info = cursor_books.fetchone()
        title = book_info[0]
        author = book_info[1]

        # Close the database connections
        cursor_members.close()
        conn_members.close()
        cursor_pending_borrowings.close()
        conn_pending_borrowings.close()
        cursor_books.close()
        conn_books.close()

        return jsonify({'message': 'Book added to pending borrowings!', 'pending_id': pending_id, 'title': title, 'author': author})
    else:
        return jsonify({'message': 'Unauthorized access.'}), 401
           
@app.route('/create_borrowing', methods=['POST'])
def create_borrowing():
    user_id = request.json.get('user_id')
    book_id = request.json.get('book_id')

    # Connect to the 'borrowings.db' database
    conn = sqlite3.connect('borrowings.db')
    cursor = conn.cursor()

    try:
        # Check if the user has al  ready borrowed the book
        cursor.execute("SELECT * FROM borrowings WHERE user_id=? AND book_id=?", (user_id, book_id))
        existing_borrowing = cursor.fetchone()

        if existing_borrowing:
            return 'You have already borrowed this book', 400

        # Create a new borrowing
        cursor.execute("INSERT INTO borrowings (user_id, book_id) VALUES (?, ?)", (user_id, book_id))
        conn.commit()  # Commit the changes to persist them in the database

        return 'Borrowing created successfully', 200
    except Exception as e:
        print(str(e))
        return 'Failed to create borrowing. Please try again.', 500
    finally:
        cursor.close()
        conn.close()

@app.route('/check_borrowings', methods=['POST'])
def check_borrowings():
    book_id = request.json.get('book_id')

    # Connect to the 'borrowed_books.db' and 'pending_borrowings.db' databases
    borrowed_conn = sqlite3.connect('borrowed_books.db')
    borrowed_cursor = borrowed_conn.cursor()

    pending_conn = sqlite3.connect('pending_borrowings.db')
    pending_cursor = pending_conn.cursor()

    try:
        # Check if the book with the given book_id is already borrowed
        borrowed_cursor.execute("SELECT COUNT(*) FROM borrowed_books WHERE book_id=?", (book_id,))
        borrowed_result = borrowed_cursor.fetchone()
        borrowed = borrowed_result[0] > 0

        # Check if the book with the given book_id is already pending
        pending_cursor.execute("SELECT COUNT(*) FROM pending_borrowings WHERE book_id=?", (book_id,))
        pending_result = pending_cursor.fetchone()
        pending = pending_result[0] > 0

        # Return the result as a JSON response
        response = {
            'borrowed': borrowed,
            'pending': pending
        }
        return jsonify(response), 200
    except Exception as e:
        print(str(e))
        return 'Failed to check borrowings. Please try again.', 500
    finally:
        borrowed_cursor.close()
        borrowed_conn.close()
        pending_cursor.close()
        pending_conn.close()

@app.route('/pending_borrowings')
def pending_borrowings():
    conn_pending_borrowings = sqlite3.connect('pending_borrowings.db')
    cursor_pending_borrowings = conn_pending_borrowings.cursor()

    # Retrieve pending borrowings
    cursor_pending_borrowings.execute('SELECT pending_id, member_id, book_id, quantity FROM pending_borrowings')

    borrowings = cursor_pending_borrowings.fetchall()

    # Format the borrowings as a list of dictionaries
    result = []
    for borrowing in borrowings:
        book_id = borrowing[2]
        quantity = borrowing[3]

        # Retrieve the book details using the book ID from the "books" table
        book = retrieve_book_by_id(book_id)

        if book:
            borrowing_data = {
                'pending_id': borrowing[0],
                'member_id': borrowing[1],
                'title': book['title'],
                'author': book['author'],
                'quantity': quantity
            }
            result.append(borrowing_data)

    conn_pending_borrowings.close()

    return json.dumps(result)

@app.route('/remove_pending_borrowing', methods=['POST'])
def remove_pending_borrowing():
    pending_id = request.json.get('borrowing_id')

    # Connect to the 'pending_borrowings.db' database
    conn = sqlite3.connect('pending_borrowings.db')
    cursor = conn.cursor()

    try:
        # Delete the pending borrowing with the given pending_id from the 'pending_borrowings' table
        cursor.execute("DELETE FROM pending_borrowings WHERE pending_id=?", (pending_id,))
        rows_affected = cursor.rowcount

        if rows_affected > 0:
            conn.commit()  # Commit the changes to persist them in the database
            return 'Pending borrowing removed successfully', 200
        else:
            return 'No pending borrowing found with the specified ID', 404
    except Exception as e:
        print(str(e))
        return 'Failed to remove pending borrowing. Please try again.', 500
    finally:
        cursor.close()
        conn.close()

@app.route('/accept_pending_borrowing', methods=['POST'])
def accept_pending_borrowing():
    pending_id = request.json.get('pending_id')

    # Update the pending_borrowings table in the database to mark the borrowing as accepted
    conn = sqlite3.connect('pending_borrowings.db', check_same_thread=False)
    cursor = conn.cursor()

    cursor.execute('DELETE FROM pending_borrowings WHERE pending_id = ?', (pending_id,))
    conn.commit()
    conn.close()

    return {'success': True}, 200

@app.route('/admin/staff/', methods=['GET', 'POST'])
def admin_staff():
    if request.method == 'POST':
        # Check if the form data contains a 'delete' parameter
        if 'delete' in request.form:
            staff_id = request.form['delete']

            # Connect to the staff database
            conn_staff = sqlite3.connect('staff.db', check_same_thread=False)
            cursor_staff = conn_staff.cursor()

            # Delete the staff member from the staff table based on the staff_id
            cursor_staff.execute("DELETE FROM staff WHERE staff_id = ?", (staff_id,))
            conn_staff.commit()

            # Close the connection to the staff database
            conn_staff.close()

            return redirect('/admin/staff')
        elif 'edit' in request.form:
            # Edit staff member form submission

            # Retrieve the staff member details from the form
            staff_id = request.form['edit']
            username = request.form['username']
            email = request.form['email']
            firstname = request.form['firstname']
            lastname = request.form['lastname']

            # Update the staff member details in the database
            conn_staff = sqlite3.connect('staff.db', check_same_thread=False)
            cursor_staff = conn_staff.cursor()
            cursor_staff.execute(
                "UPDATE staff SET username = ?, email = ?, firstname = ?, lastname = ? WHERE staff_id = ?",
                (username, email, firstname, lastname, staff_id)
            )
            conn_staff.commit()

            # Redirect to the staff members page
            return redirect('/admin/staff')
        else:
            # Retrieve the form data for creating a staff member
            print(request.form)  # Print the form data to check if it is correctly received

            # Retrieve the form data for creating a staff member
            username = request.form['username']
            email = request.form['email']
            password = '1234'
            firstname = request.form['firstname']
            lastname = request.form['lastname'] 

            # Generate a UUID for the staff_id
            staff_id = str(uuid.uuid4())

            print(username, email, firstname, lastname)  # Print the retrieved values

            # Connect to the staff database
            conn_staff = sqlite3.connect('staff.db', check_same_thread=False)
            cursor_staff = conn_staff.cursor()

            # Insert the new staff member into the staff table
            cursor_staff.execute(
                "INSERT INTO staff (staff_id, username, email, password, firstname, lastname) VALUES (?, ?, ?, ?, ?, ?)",
                    (staff_id, username, email, password, firstname, lastname))
            conn_staff.commit()

            # Close the connection to the staff database
            conn_staff.close()

        return redirect('/admin/staff')
    else:
        # Connect to the staff database
        conn_staff = sqlite3.connect('staff.db', check_same_thread=False)
        cursor_staff = conn_staff.cursor()

        # Retrieve all staff members from the staff table
        cursor_staff.execute("SELECT * FROM staff")
        staff_members = cursor_staff.fetchall()

        # Close the connection to the staff database
        conn_staff.close()

        return render_template('staff.html', staff_members=staff_members)

@app.route('/staff/dashboard')
def staff_dashboard():
    # Retrieve the staff member's information from the database
    staff_id = session['staff_id']  # Assuming you store the staff ID in the session
    conn_staff = sqlite3.connect('staff.db', check_same_thread=False)
    cursor_staff = conn_staff.cursor()
    cursor_staff.execute("SELECT * FROM staff WHERE staff_id = ?", (staff_id,))
    staff_member = cursor_staff.fetchone()
    conn_staff.close()

    # Retrieve the pending borrowings from the database
    conn_pending = sqlite3.connect('pending_borrowings.db', check_same_thread=False)
    cursor_pending = conn_pending.cursor()
    cursor_pending.execute("SELECT * FROM pending_borrowings")
    pending_borrowings = cursor_pending.fetchall()
    conn_pending.close()

    return render_template('staff_dashboard.html', staff_member=staff_member, pending_borrowings=pending_borrowings)

@app.route('/get_member_username/<member_id>', methods=['GET'])
def get_member_username(member_id):
    # Retrieve the member's username from the members database
    conn_members = sqlite3.connect('members.db', check_same_thread=False)
    cursor_members = conn_members.cursor()
    cursor_members.execute("SELECT username FROM members WHERE member_id = ?", (member_id,))
    result = cursor_members.fetchone()
    conn_members.close()

    if result:
        return result[0]  # Return the username
    else:
        return ''  # Return an empty string if member is not found

@app.route('/get_book_title/<book_id>', methods=['GET'])
def get_book_title(book_id):
    # Retrieve the book's title from the books database
    conn_books = sqlite3.connect('books.db', check_same_thread=False)
    cursor_books = conn_books.cursor()
    cursor_books.execute("SELECT title FROM books WHERE book_id = ?", (book_id,))
    result = cursor_books.fetchone()
    conn_books.close()

    if result:
        return result[0]  # Return the book title
    else:
        return ''  # Return an empty string if book is not found
    
@app.route('/admin/dashboard')
def admin_dashboard():
    # Check if the user is authenticated and is an admin
    if 'username' in session and session.get('is_admin'):
        # Connect to the books database
        conn_books = sqlite3.connect('books.db', check_same_thread=False)
        cursor_books = conn_books.cursor()

        # Retrieve the count of books listed in the library
        cursor_books.execute("SELECT COUNT(*) FROM books")
        book_count = cursor_books.fetchone()[0]

        # Close the connection to the books database
        conn_books.close()

        return render_template('admin_dashboard.html', username=session['username'], book_count=book_count)
    else:
        return redirect('/')

@app.route('/admin/members/', methods=['GET', 'POST'])
def admin_members():
    if request.method == 'POST':
        # Check if the form data contains a 'delete' parameter
        if 'delete' in request.form:
            member_id = request.form['delete']

            # Connect to the members database
            conn_members = sqlite3.connect('members.db', check_same_thread=False)
            cursor_members = conn_members.cursor()

            # Delete the member from the members table based on the member_id
            cursor_members.execute("DELETE FROM members WHERE member_id = ?", (member_id,))
            conn_members.commit()

            # Close the connection to the members database
            conn_members.close()

            return redirect('/admin/members')
        elif 'edit' in request.form:
            # Edit member form submission

            # Retrieve the member details from the form
            member_id = request.form['edit']
            username = request.form['username']
            email = request.form['email']
            phone = request.form['phone']
            birthday = request.form['birthday']
            first_name = request.form['first_name']
            last_name = request.form['last_name']

            # Update the member details in the database
            conn_members = sqlite3.connect('members.db', check_same_thread=False)
            cursor_members = conn_members.cursor()
            cursor_members.execute(
                "UPDATE members SET username = ?, email = ?, phone = ?, birthday = ?, first_name = ?, last_name = ? WHERE member_id = ?",
                (username, email, phone, birthday, first_name, last_name, member_id)
            )
            conn_members.commit()

            # Redirect to the members page
            return redirect('/admin/members')
        else:
            # Retrieve the form data for creating a member
            print(request.form)  # Print the form data to check if it is correctly received

            member_id = str(uuid.uuid4())

            # Retrieve the form data for creating a member
            username = request.form['username']
            email = request.form['email']
            phone = request.form['phone']
            birthday = request.form['birthday']
            first_name = request.form['first_name']
            last_name = request.form['last_name']

            print(username, email, phone, birthday, first_name, last_name)  # Print the retrieved values

            # Connect to the members database
            conn_members = sqlite3.connect('members.db', check_same_thread=False)
            cursor_members = conn_members.cursor()

            # Insert the new member into the members table
            cursor_members.execute(
                "INSERT INTO members (member_id, username, email, phone, birthday, first_name, last_name) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (member_id, username, email, phone, birthday, first_name, last_name))
            conn_members.commit()

            # Close the connection to the members database
            conn_members.close()

        return redirect('/admin/members')
    else:
        # Connect to the members database
        conn_members = sqlite3.connect('members.db', check_same_thread=False)
        cursor_members = conn_members.cursor()

        # Retrieve all members from the members table
        cursor_members.execute("SELECT * FROM members")
        members = cursor_members.fetchall()

        # Close the connection to the members database
        conn_members.close()

        return render_template('members.html', members=members)

@app.route('/admin/books/', methods=['GET', 'POST'])
def admin_books():
    if request.method == 'POST':
        # Check if the form data contains a 'delete' parameter
        if 'delete' in request.form:
            book_id = request.form['delete']

            # Connect to the books database
            conn_books = sqlite3.connect('books.db', check_same_thread=False)
            cursor_books = conn_books.cursor()

            # Delete the book from the books table based on the book_id
            cursor_books.execute("DELETE FROM books WHERE book_id = ?", (book_id,))
            conn_books.commit()

            # Close the connection to the books database
            conn_books.close()

            return redirect('/admin/books')
        elif 'edit' in request.form:
            # Edit book form submission

            # Retrieve the book details from the form
            book_id = request.form['edit']
            title = request.form['title']
            author = request.form['author']
            description = request.form['description']
            publisher = request.form['publisher']
            publication_date = request.form['publication_date']
            quantity = request.form['quantity']

            # Update the book details in the database
            conn_books = sqlite3.connect('books.db', check_same_thread=False)
            cursor_books = conn_books.cursor()
            cursor_books.execute(
                "UPDATE books SET title = ?, author = ?, description = ?, publisher = ?, publication_date = ?, quantity = ? WHERE book_id = ?",
                (title, author, description, publisher, publication_date, quantity, book_id)
            )
            conn_books.commit()

            # Redirect to the books page
            return redirect('/admin/books')
        else:
            # Retrieve the form data for creating a book
            print(request.form)  # Print the form data to check if it is correctly received

            # Generate a UUID for the book_id
            book_id = str(uuid.uuid4())

            # Retrieve the form data for creating a book
            title = request.form['title']
            author = request.form['author']
            description = request.form['description']
            publisher = request.form['publisher']
            publication_date = request.form['publication_date']
            quantity = int(request.form['quantity'])

            # Search for the ISBN based on the book title
            isbn = search_isbn(title)

            print(book_id, isbn, title, author, description, quantity)  # Print the retrieved values

            # Connect to the books database
            conn_books = sqlite3.connect('books.db', check_same_thread=False)
            cursor_books = conn_books.cursor()

            # Insert the new book into the books table
            cursor_books.execute(
                "INSERT INTO books (book_id, isbn, title, author, description, publisher, publication_date, quantity) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (book_id, isbn, title, author, description, publisher, publication_date, quantity))
            conn_books.commit()

            # Close the connection to the books database
            conn_books.close()

        return redirect('/admin/books')
    else:
        # Connect to the books database
        conn_books = sqlite3.connect('books.db', check_same_thread=False)
        cursor_books = conn_books.cursor()

        # Retrieve all books from the books table
        cursor_books.execute("SELECT * FROM books")
        books = cursor_books.fetchall()

        # Close the connection to the books database
        conn_books.close()

        return render_template('books.html', books=books)

# Function to calculate the expected return date based on the due date
def calculate_return_date(due_date):
    due_date_obj = datetime.strptime(due_date, '%Y-%m-%d')
    return due_date_obj + datetime.timedelta(days=14)  # Assuming a borrowing period of 14 days

# Function to generate a unique borrow ID
def generate_borrow_id():
    return str(uuid.uuid4())

@app.route('/borrow', methods=['POST'])
def borrow_book():
    # Check if the user is authenticated and not an admin
    if 'username' in session and not session.get('is_admin'):
        # Get the book details from the form submission
        book_id = request.form['book_id']
        due_date = request.form['due_date']
        quantity = int(request.form['quantity'])
        
        # Perform validation on the input data
        if not book_id or not due_date or quantity <= 0:
            flash('Invalid input. Please provide all the required details.')
            return redirect('/user/dashboard')
        
        # Retrieve the book from the database
        conn = sqlite3.connect('books.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM books WHERE book_id = ?', (book_id,))
        book = cursor.fetchone()
        
        # Check if the book exists and has sufficient quantity
        if book and book[7] >= quantity:  # Assuming quantity is stored at index 7
            # Calculate the expected return date
            expected_return_date = calculate_return_date(due_date)
            
            # Perform the book borrowing process
            conn = sqlite3.connect('borrowed_books.db')
            cursor = conn.cursor()
            for i in range(quantity):
                # Generate a unique borrow ID
                borrow_id = generate_borrow_id()
                
                # Insert the borrowed book into the database
                cursor.execute('INSERT INTO borrowed_books (borrow_id, book_id, username, due_date, expected_return_date) VALUES (?, ?, ?, ?, ?)',
                               (borrow_id, book_id, session['username'], due_date, expected_return_date))
            
            # Update the quantity of the book in the books database
            updated_quantity = book[7] - quantity  # Assuming quantity is stored at index 7
            cursor.execute('UPDATE books SET quantity = ? WHERE book_id = ?', (updated_quantity, book_id))
            
            conn.commit()
            conn.close()
            
            flash('Book(s) borrowed successfully.')
            return redirect('/user/dashboard')
        else:
            flash('Book is not available or quantity is insufficient.')
            return redirect('/user/dashboard')
    else:
        return redirect('/')
    
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        member_id = str(uuid.uuid4())
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']
        birthday = request.form['birthday']
        firstname = request.form['firstname']
        lastname = request.form['lastname']

        # Connect to the members database
        conn = sqlite3.connect('members.db', check_same_thread=False)
        cursor = conn.cursor()

        # Insert the new registrant into the members table
        cursor.execute(
            "INSERT INTO members (member_id, username, email, password, phone, birthday, firstname, lastname) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (member_id, username, email, password, phone, birthday, firstname, lastname))
        conn.commit()

        # Close the connection to the members database
        conn.close()

        return redirect('/')
    else:
        return render_template('register.html')

@app.route('/logout')
def logout():
    # Clear the session data
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run()
