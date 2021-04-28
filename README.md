# ToDos
A Flask and SQLite based CRUD demo page. Inspired by [this](https://www.youtube.com/watch?v=Z1RJmh_OqeA) video.
The aim here is to build a simple Flask-SQLite-CRUD reference.

You can initialize the SQLite database by setting environment variable `SQLITE_INIT` to `True`

# Celebrities
A Flask and MongoDB Atlas CRUD demo page. Inspired by the code along mini project by the same name in the Code Institute curriculum.

You can initialize the MongoDB collection by setting environment variable `MONGO_INIT` to `True`

# Love Sandwiches
A Flask and Google Sheets API demo page. Inspired by the code along mini project by the same name in the Code Institute curriculum.

### How To Run the application
1. Install `virtualenv`:
```
$ pip install virtualenv
```
2. Open a terminal in the project root directory and run:
```
$ virtualenv env
```
3. Then run the command:
```
$ .\env\Scripts\activate
```
4. Then install the dependencies:
```
$ (env) pip install -r requirements.txt
```
5. Finally start the web server:
```
$ (env) python app.py
```

The application is deployed on [Heroku](https://todo-celeb-sandwic-ruszkipista.herokuapp.com/)