# [My Car Administration](https://my-car-ruszkipista.herokuapp.com/)
Track the cost and fuel consumption of the fleet of cars in the family! While recording transactions is straightforward for all family members, there are administrative aspects of the database, which need steady hands. Hence I wrote this CRUD web application to maintain the My Car app's database. Inspired by my own car cost tracking spreadsheets. (the My Car app itself is a separate development endeavour). 

My aim with this project is to demonstrate backend development skills, REST API usage and CRUD operations on Non-SQL database. It is written in Python using Flask and MongoDB-Atlas, styled with Material Design Bootstrap. This project is my third milestone in obtaining the [Full Stack Web Development](https://codeinstitute.net/full-stack-software-development-diploma/) diploma from [Code Institute](https://codeinstitute.net/)

![the web page on different devices](./docs/responsive-am-i.png "the web page on different size devices")

A live demo can be found - [here](https://my-car-ruszkipista.herokuapp.com/), use username/password: user1/user1 for a normal user or admin/admin for an administrator.

The Project Repository can be found - [here](https://github.com/ruszkipista/cims03-my-car)

## Contents
- [0. Data structures design](#0-data-structures-design "0. Data structures design")
- [1. User experience design](#1-user-experience-design "1. UX design")
  - [1.1 Strategy Plane](#11-strategy-plane "1.1 Strategy Plane")
  - [1.2 Scope plane](#12-scope-plane "1.2 Scope plane")
  - [1.3 User Stories](#13-user-stories "1.3 User Stories")
  - [1.4 Structure plane](#14-structure-plane "1.4 Structure plane")
  - [1.5 Skeleton plane](#15-skeleton-plane "1.5 Skeleton plane")
  - [1.6 Surface plane](#16-surface-plane "1.6 Surface plane")
- [2. Code design](#2-code-design "2. Code design")
- [3. Features Left to Implement](#3-features-left-to-implement "3. Features Left to Implement")
- [4. Technologies and Tools Used](#4-technologies-and-tools-used "4. Technologies and Tools Used")
- [5. Issues](#5-issues "5. Solved and Known issues")
- [6. Testing](#6-testing "6. Testing")
- [7. Deployment](#7-deployment "7. Deployment")
- [8. Credits](#8-credits "8 Credits")

## 0. Data structures design
Let's briefly introduce the data structures of the My Car application. It is necessary to learn some features to understand the reason behind arrangements in the data.

The main entity is the Car. We want to collect financial transactions occurring around cars in order to answer such questions
- What is the fuel economy look like, how much fuel it consumes on a set distance or how much distance it can take on a set amount of fuel?
- How much do we spend on the car to run daily, monthly, yearly?
- How much does it cost to run 100 km?
- How much is the book value of the car today?

Here is the database schema in relational terms:
![database schema](./docs/my-car-db-diagram.png "My Car database schema")

### 0.1 Transaction
So in order to calculate all of that, we need to record the following things about a Transaction:
- which car it relates to,
- when did it happen
- who was the business partner on the other end of the transaction
- description to record details which does not conform to any other transaction details
- what material/service was involved - to be able to separate operating and capital expenses
- how much quantity and what unit  - for various reasons
- What was the price in what currency? - for expense calculation
- to keep track the run distances between refuellings, we need the status of the odometer when it happened

### 0.2 Car
In the Car entity we need a couple of identifiers:
- a picture for visuals
- a name and description
- a plate number for official records

For keeping track of the distance run and calculate fuel consumption:
- in what country was the car registered in - this determines the reporting currency, in which currency the car's statistics are aggregated
- unit of the odometer, is it km or miles?
- what fuel material do we need: petrol or gasoline? or perhaps electricity? - this can pull in the fuel material into the transaction
- what unit do we want to see the fuel consumption in: L/100km or miles/gallon?

### 0.3 Country
To be able to record registration country, we need the Country entity, in which we store
- country's standard sign. e.g. IE, HU
- description
- official currency for payment - this can go into the transaction as default value
- official distance keeping unit on roads, e.g. km for IE, miles for NI
- in what unit the liquid fuel sold, liter or gallon?

### 0.4 Currency
To be able to record fiscal values in different countries, we need to set up Currencies:
- 3 characters ISO designation,
- description
- 1 or 2 character short sign in local abbreviation or characters

### 0.5 Currency Conversions
If we take the car out of the registration country, we might need to pay in a different currency. To be able to aggregate fiscal values in the registration country's currency, we need to convert currency values, hence the Currency Conversions collection which consist of
- validity date of the conversion rate
- source currency
- target currency
- exchange rate: unit source currency value expressed in target currency value, e.g. 1 EUR => 0.89080 GBP on 01/01/2018

For simplicity, we allow the conversion calculation in both directions, e.g the GBP->EUR rate will serve for the EUR->GBP conversion as well. Furthermore, any rate is valid from the validity date until a newer rate is recorded. This way we do not need a rate for every day, but we could have.

### 0.6 Image
This is a collection only concerned about images. It stores them in the DB as opposed to a possible file system storage. This puts a limit on possible file sizes of 5MB. If an entity has an image associated, this collection provides a unique ID for that entity so the image will not be stored in the entity itself.
- Images also stores the original file name the image was uploaded with

### 0.7 User-Car
A car can be driven by several people. To distinguish which user can record transactions to which car, we need a User-Car relationship record. In that we store
- the user
- the car
- the relationship the user has with a car

### 0.8 Relationship Type
The relationship of a user with a car is described with a Relationship Type, utilized in Users-Cars collection. It is a simple lookup table with
- relationship name
- relationship description

### 0.9 Partner
A Parter identifies a business or government entity who we paid for goods or service. It has
- name
- description
- country - this pulls in the default currency into the transaction recording
- address - this clarifies, exactly in which Tesco store we bought the windscreen wiper

### 0.10 Material
This is the thing we buy or pay for during a transaction. We keep it simple, oly have 3 fields:
- material name
- description
- material type - allows grouping of materials of the same type

### 0.11 Expenditure Type
The Expenditure Types has 2 entries so far
|Expenditure Name|Description|
|:--------------:|:----------|
|OP|operational expense|
|CAP|capital expense|

### 0.12 Material Type
The Material Type gives two attribute to materials:
- measure type: how do we measure the quantity, e.g. by volume or distance?
- in what part of the expense calculation we will aggregate the value paid for this type of material: capital or operating expense

Also we need
- material type name
- material type description

### 0.13 Measure Type
Measure Type determines the approach to how we measure something. These are the entries in the Measure Types collection:

|Measure Type Name|Description|
|:---------------:|:----------|
|CNT |count|
|VOL |volume|
|MASS|mass|
|DIST|distance|
|AREA|area|
|FECO|fuel economy|
|CURR|currency|
|TIME|time|

### 0.14 Unit of Measure
> A unit of measurement is a definite magnitude of a quantity 
> -- from [wikipedia](https://en.wikipedia.org/wiki/Unit_of_measurement)

We use it in quantifying the purchase, the distance taken, the fuel consumption, etc. For us it is
- a name,
- a description,
- and a measure type

Here are 2 example records from the collection:

|Name|Description|Measure Type|
|:--:|:----------|:-----------|
|km|Kilometre|DIST|
|L|Litre|VOL|

### 0.15 Unit Conversion
When we have two Unit of Measures of the same type, we want to know how many units of A equals units of B. This collection stores some prominent conversion rates, like `km` <-> `miles`
- source unit of measure
- target unit of measure
- conversion factor

### 0.16 User
We see earlier, that if we want users to restrict access to cars, we set up User-Car relationships. The User part from that is identified here:
- user name - for identification in the app
- password - secret key for authentication
- does the user have administrative privileges
- who created or later modified this user record
- when was the last change on this user record

### 0.17 Fieldcatalog
The data structure descriptors of every collection are stored in the Fieldcatalog collection. The following example describes the User entity.
```JSON
{ "collection_name": "users",
  "entity_name":     "user",
  "description":     "Users",
  "admin":           true,
  "buffered":        true,
  "fields": [
    { "name": "username",         "heading": "User Name",      "input_type": "text",      "unique": true },
    { "name": "password",         "heading": "Password",       "input_type": "password",  "attributes": "autocomplete=new-password" },
    { "name": "user_is_admin",    "heading": "Administrator?", "input_type": "checkbox" },
    { "name": "date_time_insert", "heading": "Registered",     "input_type": "timestamp_insert" },
    { "name": "date_time_update", "heading": "Updated",        "input_type": "timestamp_update" },
    { "name": "changed_by",       "heading": "Changed By",     "input_type": "changedby", "values": "users" }
  ],
  "select_field": "username"
}
```

### 0.18 Note on foreign keys
The data is stored in a Mongo database where the unit of storage is *document*. Every document has a unique identifier, in the DB it has the `_id` name. The documents are stored in *collections*. In our data structure we equate an entity representative with a document. E.g. one Car is stored as a document. Many representatives of the same entity are stored in the Cars collection.

If one entity refers to another entity with an attribute, we call that attribute as foreign key. E.g. one User-Car relationship contains 3 foreign keys: User, Car and Relationship Type. We store these references to the foreign entities by their `_id`
So instead of having a (`user_id`:`user1`, `car_id`:`yaris`, `relationship_id`:`owner`) we store (`user_id`: `611986fa17a24010b762fd6c`, `car_id`: `611986fe17a24010b762fd7c`, `relationship_id`: `611986f917a24010b762fd69`) where 611986fa17a24010b762fd6c refers to the `_id` of `user1` in Users, `611986fe17a24010b762fd7c` refers to the `_id` of `yaris` in Cars and `611986f917a24010b762fd69` refers to the `_id` of `owner` in Relationship Types.

## 1. User Experience design
### 1.1 Strategy Plane
Stakeholders of the website:
- members of a family or employee of small enterprise with a pool of cars
- chosen persons to perform certain database entry maintenance for the benefit of other users within the group
- developer of the My Car application

#### 1.1.1 Goals and Objectives of Stakeholders (users)
|User|Goals, Needs, Objectives|
|----|------------------------|
|all|facilitate the maintanence on a computer screen of data under the My Car application|
|all|only authorized user may modify data in the database|
|normal|allow to maintain the Partners and Transactions collections, but nothing else|
|normal|normal user can only record Transactions for cars assigned to them|
|admin|allow to perform every operation what and how a normal user can do|
|admin|allow to maintain every data in the database|
|developer|users can not modify the data structures of the My Car app|
|developer|keep the admin functionality flexible, so future enhancements in data would require minimal changes here|

### 1.2 Scope plane
It has been decided to create a web application to serve and fulfill the goals and needs of the users.

This is the list of planned features:

- users are identified by user name, it must be unique in the Users collection
- users are authenticated by entered username/password against stored values at log in
- a username and a password can be 5-15 characters long
- users can log out
- new normal user can be registered, an administrative user can not be registered
- a normal user can be promoted to an administrator user
- an administrator can be demoted to a normal user
- a normal user can change its own password
- an administrator user can change any user's password in the Users collection
- a normal user can create, modify or delete any record in Partners collection
- a normal user can create, modify or delete records in Transactions if the Transaction's car associated with the User in the Users-Cars collection
- the list of Transactions on the Maintain Transactions page can be filtered with single car values, but only those Cars can be selected which are associated with the User in the Users-Cars collection
- an administrative user can create, modify or delete any record in any collection
- every web page has a sticky navigation bar on the top of the page
- every page has a flash messages section which is only revealed if the previous operation generated one or more messages
- the Home page without logged in user shows no information from the database
- the Home page with logged in user shows links in the navbar to the maintenance of Partners and Transactions collections
- the Home page with logged in user shows a list of Cars and their data
- the Home page with logged in *administrative* user also provides links for the maintenance of all collections
- the Maintenance page of any collection has a uniform way of listing existing records, creating a new record, modifying an existing record or deleting an existing record
- a deletion of a record must be preceded with a request of confirmation
- a deletion is performed in isolation regardless if the record itself is still referenced in another record somewhere else
- in an input field, which is a foreign key, a value is presented which the foreign key refers to (not the foreign key value itself)
- every REST API endpoint needs to be protected (where it makes sense) by checking if there is a valid user logged in

### 1.3 User Stories
* As a ... I want to ..., so I can ...

As a visitor (without logging in), 
- I am not able to log in without registered username/password, so I can not modify the database content
- I want to register with a username and password, so I can become a normal user
- I am not able to register an already taken username
- I am not able to maintain any data by entering the sub-page's URL address

As a user, I want
- the website content consumable on computer screen and mobile devices, so I can use it on any device I have access to
- to log in with my username and valid password only, so others can not login with invalid password
- to filter transactions with a selected car, so I can easier check their list without confusion
- to have an image stored about all carr, so I can quickly identify their data in lists

As logged in user, I want to
- Log Out, so no one can modify the database under my username without my knowledge
- change my own password, so I can service myself
- create/modify/delete business partners, so I can record a transaction with new partner or correct my mistake at Partner creation
- record Transactions for those cars only which are associated with me, so I can not maintain transactions for an unassigned car by mistake.

As a logged in administrator user, I want to
- create/modify/delete records in any of the collections, so I can serve other users' data modification needs
- promote a normal user to administrator, so I can share the admin work with someone else.
- demote an admin user back to normal user status, so the user can not make any more administrative mistakes.
- create a new user, so the person can log into the application
- I am not able to record an already taken username, so there won't be confusion at the login process
- reset a user's forgotten password, so they can log in again
- assign a car to a user, so the setting can follow real world changes
- deassign a car from a user, so the setting can follow real world changes
- replace an image in Images collection, so I can serve such user requests

### 1.4 Structure plane
The structure of the website to be built consist of these pages:
- Home page in 3 variants: no user not logged in / normal user logged in /  admin user logged in
- RegLog page in 2 variants: Log In / Register User
- Profile page
- Maintain &lt;collection&gt; page in 16 variants, where collection can be: Transactions / Partners / Users / Images / Currencies / Currency Rates / Measure Types / Unit of Measures / Unit Conversions / Countries / Expenditure Types / Material Types / Materials / Cars / Relationship Types / Users-Cars
- Update &lt;entity&gt; page in 16 variants, where entity can be: Transaction / Partner / User / Image / Currency / Currency Rate / Measure Type / Unit of Measure / Unit Conversion / Country / Expenditure Type / Material Type / Material / Car / Relationship Type / Users-Car

The following navigation links are left off from the diagram below:
- Home: available on all pages
- Log Out, Partners, Transactions: once logged in, every page contains these links in the navbar

<p style="text-align: center;"><img src="./docs/my-car-website-structure.png" alt="Website structure" title="pages with navigation links"><p>

### 1.5 Skeleton plane

<details>
  <summary>Home page - Features and Wireframes</summary>

<h3>Home page - User Not Logged In</h3>

|Section|Feature / Content description|
|--------------|-----------------------------|
|Navbar|Link "My Car" - link to Home page|
|Navbar|Link "Home" - link to Home page|
|Navbar|Link "Log In" - link to Log In page|
|Header|Flash Message: Contains message(s) if the previous operation issued one. Their type can be: Information (light blue), Success (green), Warning (yellow) and Error (red)"|
|Header|Title: "My Car Administration"|
|Main|a centered sizeable car icon|

<br>
<img width="100%" src="./docs/my-car-wireframe-home1.png" alt="Wireframe-Home page 1" title="Home page - User not logged in">

<h3>Home page - Admin User Logged In</h3>

|Section|Feature / Content description|
|--------------|-----------------------------|
|Path|`/`|
|Navbar|Link "My Car" - link to Home page|
|Navbar|Link "Home" - link to Home page|
|Navbar|Link "Partners" - link to Maintain Partners page|
|Navbar|Link "Transactions" - link to Maintain Transactions page|
|Navbar|Link "Profile" - link to Profile page|
|Navbar|Link "Log Out" - link to Log Out from the application|
|Header|Flash Message: Contains message(s) if the previous operation issued one. Their type can be: Information (light blue), Success (green), Warning (yellow) and Error (red)"|
|Header|Buttons listed horizontally: USERS, IMAGES, CURRENCIES, CURRENCY RATES, MEASURE TYPES, UNIT OF MEASURES, UNIT CONVERSIONS, COUNTRIES, EXPENDITURE TYPES, MATERIAL TYPES, MATERIALS, CARS, RELATIONSHIP TYPES, USERS-CARS - all links to the corresponding Maintain &lt;collection&gt; page|
|Header|Title: "Cars assigned to you". Hidden if no car is assigned to user|
|Main|Table: list of car records from Cars collection, which are assigned to the logged in user via a record in Users-Cars collection. The first column of the table is filled with the car images. Hidden if no car is assigned to user|

<br>
<img width="100%" src="./docs/my-car-wireframe-home2.png" alt="Wireframe-Home page 2" title="Home page - Admin User Logged In">

<h3>Home page - Normal User Logged In</h3>

|Section|Feature / Content description|
|--------------|-----------------------------|
|Path|`/`|
|Navbar|Link "My Car" - link to Home page|
|Navbar|Link "Home" - link to Home page|
|Navbar|Link "Partners" - link to Maintain Partners page|
|Navbar|Link "Transactions" - link to Maintain Transactions page|
|Navbar|Link "Profile" - link to Profile page|
|Navbar|Link "Log Out" - link to Log Out from the application|
|Header|Flash Message: Contains message(s) if the previous operation issued one. Their type can be: Information (light blue), Success (green), Warning (yellow) and Error (red)"|
|Header|Title: "Cars assigned to you". Hidden if no car is assigned to user|
|Main|Table: list of car records from Cars collection, only those, which are assigned to the logged in user via a record in Users-Cars collection. The first column of the table is filled with the cars images. Hidden if no car is assigned to user|

<br>
<img width="100%" src="./docs/my-car-wireframe-home3.png" alt="Wireframe-Home page 3" title="Home page - Normal User Logged In">

</details>

<details>
  <summary>Reg/Log page - Features and Wireframes</summary>

<h3>Log In page</h3>

|Section|Feature / Content description|
|--------------|-----------------------------|
|Path|`/login`|
|Navbar|Link "My Car" - link to Home page|
|Navbar|Link "Home" - link to Home page|
|Navbar|Link "Log In" - link to Log In page|
|Header|Flash Message: Contains message(s) if the previous operation issued one. Their type can be: Information (light blue), Success (green), Warning (yellow) and Error (red)"|
|Header|Title: "Log In"|
|Main|Input field - "Username" - empty, minimum 5, maximum 15 characters long|
|Main|Input field - "Password" - empty, minimum 5, maximum 15 characters long|
|Main|Button - "LOG IN" - link to logging in the given user|
|Main|Text: "New Here?", Link: "Register Account" - link to Register User page|

<h3>Register User page</h3>

|Section|Feature / Content description|
|--------------|-----------------------------|
|Path|`/register`|
|Navbar|Link "My Car" - link to Home page|
|Navbar|Link "Home" - link to Home page|
|Navbar|Link "Log In" - link to Log In page|
|Header|Flash Message: Contains message(s) if the previous operation issued one. Their type can be: Information (light blue), Success (green), Warning (yellow) and Error (red)"|
|Header|Title: "Register User"|
|Main|Input field - "Username" - empty, minimum 5, maximum 15 characters long|
|Main|Input field - "Password" - empty, minimum 5, maximum 15 characters long|
|Main|Button - "REGISTER" - link to logging in the given user|
|Main|Text: "Already Registered?", Link: "Log In" - link to Log In page|

<br>
<img width="100%" src="./docs/my-car-wireframe-reglog.png" alt="Wireframe-Register/LogIn pages" title="Register User / Log In pages">

</details>

<details>
  <summary>Profile page - Features and Wireframes</summary>

<h3>Profile page</h3>

|Section|Feature / Content description|
|--------------|-----------------------------|
|Path|`/profile`|
|Navbar|Link "My Car" - link to Home page|
|Navbar|Link "Home" - link to Home page|
|Navbar|Link "Partners" - link to Maintain Partners page|
|Navbar|Link "Transactions" - link to Maintain Transactions page|
|Navbar|Link "Profile" - link to Profile page|
|Navbar|Link "Log Out" - link to Log Out from the application|
|Header|Flash Message: Contains message(s) if the previous operation issued one. Their type can be: Information (light blue), Success (green), Warning (yellow) and Error (red)"|
|Header|Title: "Profile of &lt;username&gt;"|
|Header|Title2: "Change Password"|
|Main|Input field - "Old Password" - empty|
|Main|Input field - "New Password" - empty|
|Main|Button - "CHANGE PASSWORD" - link to changing the password of the logged in user|

<br>
<img width="100%" src="./docs/my-car-wireframe-profile.png" alt="Wireframe-Profile page 1" title="Profile page">

</details>

<details>
  <summary>Maintain page - Features and Wireframes</summary>

<h3>Maintain page - Overview &lt;collection&gt; records</h3>

|Section|Feature / Content description|
|--------------|-----------------------------|
|Path|`/maintain/<collection>`|
|Navbar|Link "My Car" - link to Home page|
|Navbar|Link "Home" - link to Home page|
|Navbar|Link "Partners" - link to Maintain Partners page|
|Navbar|Link "Transactions" - link to Maintain Transactions page|
|Navbar|Link "Profile" - link to Profile page|
|Navbar|Link "Log Out" - link to Log Out from the application|
|Header|Flash Message: Contains message(s) if the previous operation issued one. Their type can be: Information (light blue), Success (green), Warning (yellow) and Error (red)"|
|Header|Title: "Maintain &lt;collection&gt;"|
|Main|Closed Accordion item header: Title: "New &lt;entity&gt;" - header linked to the opening up of the accordion item|
|Main|Table: list of collection records. For each record the last column contains two icons linked to the update or delete of the record. Hidden if there are no records in the collection|

<br>
<img width="100%" src="./docs/my-car-wireframe-maintain1.png" alt="Wireframe-Maintain page 1" title="Maintain page - Overview &lt;collection&gt; records">

<h3>Maintain page - Add new &lt;entity&gt;</h3>

|Section|Feature / Content description|
|--------------|-----------------------------|
|Path|`/maintain/<collection>`|
|Navbar|Link "My Car" - link to Home page|
|Navbar|Link "Home" - link to Home page|
|Navbar|Link "Partners" - link to Maintain Partners page|
|Navbar|Link "Transactions" - link to Maintain Transactions page|
|Navbar|Link "Profile" - link to Profile page|
|Navbar|Link "Log Out" - link to Log Out from the application|
|Header|Flash Message: Contains message(s) if the previous operation issued one. Their type can be: Information (light blue), Success (green), Warning (yellow) and Error (red)"|
|Header|Title: "Maintain &lt;collection&gt;"|
|Main|Open Accordion item header: Title: "New &lt;entity&gt;" - header linked to the opening up of the accordion item|
|Main|Open Accordion item body: Contains empty input fields, one for each field in an entity. The fields can have the following types: Text, Number, Date, Select (drop-down), Checkbox, Password, Image, Timestamp (hidden), ChangedBy (hidden). All field content is initial|
|Main|Table: list of collection records. For each record the last column contains two icons linked to the update or delete of the record. Hidden if there are no records in the collection|

<br>
<img width="100%" src="./docs/my-car-wireframe-maintain2.png" alt="Wireframe-Maintain page 2" title="Maintain page - Add new <entity>">

<h3>Maintain page - Update an &lt;entity&gt;</h3>

|Section|Feature / Content description|
|--------------|-----------------------------|
|Path|`/update/<collection>/<record_id>`|
|Navbar|Link "My Car" - link to Home page|
|Navbar|Link "Home" - link to Home page|
|Navbar|Link "Partners" - link to Maintain Partners page|
|Navbar|Link "Transactions" - link to Maintain Transactions page|
|Navbar|Link "Profile" - link to Profile page|
|Navbar|Link "Log Out" - link to Log Out from the application|
|Header|Flash Message: Contains message(s) if the previous operation issued one. Their type can be: Information (light blue), Success (green), Warning (yellow) and Error (red)"|
|Header|Title: "Maintain &lt;entity&gt;"|
|Main|Open Accordion item header: Title: "Update &lt;entity&gt;" - header linked to the opening up of the accordion item|
|Main|Open Accordion item body: Contains empty input fields, one for each field of the entity. The fields can have the following types: Text, Number, Date, Select (drop-down), Checkbox, Password, Image, Timestamp (hidden), ChangedBy (hidden). All fields are filled from the record previously selected for update|

<br>
<img width="100%" src="./docs/my-car-wireframe-maintain3.png" alt="Wireframe-Maintain page 3" title="Maintain page - Update an <entity>">

</details>

### 1.6 Surface plane
Choose default settings of MDBootstrap:
- font family `Roboto`
- class `bg-secondary` (purple) for administrator user's navbar background color
- class `bg-primary` (blue) for normal user's navbar background color
- class `bg-warning` (orange) for the accordion header background color

## 2. Code design
* utilizing the [Flask](https://flask.palletsprojects.com/) framework for handling REST API calls
  - The `run.py` file contains code related to Flask only, no database or form reference can appear in there.
  - The `formdb.py` file is a module and contains code related to the database and web page forms.
* generating web pages from HTML templates with [Jinja](https://jinja.palletsprojects.com/) templating inserts
  - the `base.html` file contains the base HTML structure of all web pages generated in the app
  - the `index.html` extends the `base.html` into the 3 versions of the Home page
  - the `reglog.html` extends the `base.html` into the Login and Register User pages
  - the `profile.html` extends the `base.html` into the Profile page
  - the `maintain.html` extends the `base.html` into the 32 versions of the Maintain page: 16 collections * (`/maintain/<collection>` + `/update/<collection>/<record_id>`)
* The database structure and content can be initialized programmatically. It is governed by the environment variable `MONGO_INIT`. If it equals `True`, then the content of every collection is deleted and initialized using 2 project files.
  - `db_base.json` contains the entity structure descriptions (which are deposited in the Fieldcatalog) and selected basic content)
  - `db_base.json` demo content with 3 users, 3 cars and some recorded transactions)

## 3. Features Left to Implement
* develop a "view" field catalog functionality to enable calculated columns on the generated tables, e.g. fuel consumption column
* on the "Home" page instead of listing the car records from the "Cars" collection, list cars with the following calculated statistics:
  * picture of car
  * car's current book value: based on initial purchase price, planned length of keep, capital expense type of transactions recorded
  * daily cost: value based on planned amortization and operational expense type transactions
  * 100km cost: value based yearly cost and planned yearly distance run
  * last fuelling date
  * dues in the next 30 days (insurance, tax, car inspection, etc.)
* on the "Maintain Unit Conversions" page, when an option is chosen on "Source Unit" field, restrict the options of Target Unit to the same Unit type as the "Source Unit" has. E.g. selection "L" in one field would restrict the other field to VOL type units only.
* on the "Maintain Transactions" page
  * store the car filter value in the session cookie
  * add transaction date filter to the header, store this filter value in the session cookie
  * when creating a new transaction, fill the Date field with current date
  * when creating a new transaction and buying fuel type material, fill the Odometer field with the last known value
  * after selecting an option on the "Car" field, fill the "Currency" field from the "Car"->"Country"->"Currency" derivation
  * after selecting a "Goods/Service" material, derive the "Unit" field from the "Material"'s record
* allow uploading an image for every transaction and store them
* from an uploaded fuel purchase receipt extract partner/quantity/price data with machine learning character recognition (and possibly with help of receipt templates)

## 4. Technologies and Tools Used

- The project's product (the website) was written in HTML, CSS, JavaScript, Python, Jinja, utilising [Flask](https://flask.palletsprojects.com/) and [Material Design Bootstrap](https://mdbootstrap.com/) frameworks. 
- Manipulated images with program [Paint.NET](https://www.getpaint.net/). Mainly used for cropping and resizing.
- Created wireframes with program from [balsamiq](https://balsamiq.com/wireframes/)
- Edited the code with [Visual Studio Code](https://code.visualstudio.com/).
- Managed code versions with [Git](https://git-scm.com/downloads)
- Stored the code versions and project deliverables on [Github](https://github.com/) cloud service.
- Deployed the website on [Heroku](https://heroku.com/) cloud service.
- The development machine run [Windows 10](https://www.microsoft.com/en-us/software-download/windows10) operating system.
- The website was tested on desktop on [Chrome](https://www.google.com/intl/en_ie/chrome/) and [Firefox](https://www.mozilla.org/en-US/firefox/) web browsers, also on a [Asus Google Nexus 7 (2013)](https://www.gsmarena.com/asus_google_nexus_7_(2013)-5600.php) tablet running [Android OS](https://www.android.com/) and mobile [Chrome](https://play.google.com/store/apps/details?id=com.android.chrome&hl=en) browser.
- Generated favicon with [Favicon & App Icon Generator](https://www.favicon-generator.org/)
- Generated tables for this readme with [Tables Generator](https://www.tablesgenerator.com/) web service
- Generated one image (on top of this Readme) of how the website looks on different size devices with [Am I Responsive](http://ami.responsivedesign.is/)
- Searched the internet to find content, documentation and solutions for issues using [Google](https://www.google.com)'s search service.

## 5. Issues
### Issues solved during development
* on the `maintain.html` page there is one modal pop-up embedded for record deletion confirmation. The suggestion I received was to have as many modals as many rows are generated on the page. I successfully generalized the modal with a javascript function, so one modal is enough.
* separated the web server (Flask) code part from the form-database codes
### Known issues
* "Unit Conversions" collection is sorted by `*_id` foreign key fields and not by the referred foreign value `Unit Name`. Although this still groups values together, but not alphabetically sorts as one would expect. To solve it, the sorting needs to be moved from the DB into the application.
* input form and database related codes are co-dependent, because there is only one set of field names which are used by both code parts. An additional logic needs to be written to discover records still referencing the record to be deleted and do a cascading deletion.

## 6. Testing
First step in testing was the validation of HTML, CSS and JS code with [Markup Validation Service](https://validator.w3.org/), [CSS Validation Service](https://jigsaw.w3.org/css-validator/), [JS Hint](https://jshint.com/) respectively. 
The whole testing was conducted manually on a Windows 10 desktop device running Chrome browser on a 1920x1080 resolution screen and on an Android tablet. Not tested on mobile phones, because the limited screen estate does not allow wide tables handling comfortably.

See the whole <a href="https://ruszkipista.github.io/cims03-my-car/my-car-test-suite.html" target="_blank">test suite</a> in a web page.

<details>
  <summary>Test results</summary>

| Testing the My Car Administration web application                                |Result|
|:---------------------------------------------------------------------------------|:----:|
| Check landing page (Home) without logged in user on narrow screen                | pass |
| Check Home page without logged in user on wide screen                            | pass |
| **Users collection**                                                             | ---- |
| Try to Login with a non existing username:                                       | pass |
| Register a new (not already existing) user:                                      | pass |
| As logged in normal user Log Out                                                 | pass |
| Try to register a user with existing username:                                   | pass |
| Log in as normal user without car assigned                                       | pass |
| Try to log In as normal user with wrong password:                                | pass |
| Log In as administrator:                                                         | pass |
| Logged in as administrator, check records in Users collection                    | pass |
| Logged in as administrator, promote a normal user to administrator               | pass |
| Log in as an administrator user and demote itself to a normal user               | pass |
| Log in as normal user and change own password                                    | pass |
| As normal user with changed password try to log in with old password             | pass |
| As normal user with changed password try to log in with new password             | pass |
| As administrator reset a normal user???s password                                  | pass |
| Log in as normal user whose password were changed by administrator               | pass |
| Try to maintain Users using the /maintain/users address                          | pass |
| As administrator delete a normal user                                            | pass |
| Try to log in with deleted normal user                                           | pass |
| As administrator create a new normal user                                        | pass |
| As administrator try to create a user with existing username                     | pass |
|**Relationship Types, Cars, Users-Cars, Images, Partners, Transactions collections**|----|
| As administrator check Relationship Types                                        | pass |
| As administrator assign first car to a normal user                               | pass |
| Log in as normal user with a car (just) assigned                                 | pass |
| As normal user record first transaction on newly assigned car                    | pass |
| As administrator assign a second car to a normal user                            | pass |
| As normal user record a new partner                                              | pass |
| As normal user check transactions                                                | pass |
| As normal user record a new transaction on second car                            | pass |
| As administrator delete a car record                                             | pass |
| As administrator replace an image in Images                                      | pass |
| As administrator remove user-car relationship                                    | pass |
| **Currencies, Currency rates collections**                                       | ---- |
| As administrator add a new currency                                              | pass |
| As administrator record currency rates                                           | pass |
| **Measure Types, Unit of Measures, Unit Conversions collections**                | ---- |
| As administrator add a new measure type                                          | pass |
| As administrator add a new unit of measure                                       | pass |
| As administrator modify a unit of measure                                        | pass |
| As administrator add a new unit conversion                                       | pass |
| **Countries and Expenditure Types collections                                    | pass |
| As administrator change a Country setting                                        | pass |
| As administrator check Expenditure Types settings                                | pass |
| **Material Types and Materials collections**                                     | ---- |
| As administrator check Material Types settings                                   | pass |
| As administrator add a new material                                              | pass |
| As administrator modify a material                                               | pass |

No additional bugs were discovered during the final testing.

</details>

## 7. Deployment
 
### Deployment in development environment

#### 7.0 Python and Git
Make sure, that [Python](https://www.python.org/downloads/) and [Git](https://git-scm.com/downloads) are installed on your computer

### 7.1 Set up the MongoDB-Atlas hosted database

* Sign up for a free account on [MongoDB](https://www.mongodb.com/)
* create a new organisation and a new project
* inside the project at Database Deployments, create a new cluster
  * choose Shared / free tier cloud provider and region / M0 tier / choose cluster name
* inside the newly created cluster create a database, e.g. `my_car`
* in Deployment Security / Database Access, create a user with password authentication, select role `readWriteAnyDatabase`

Note down the following details:
- cluster name
- database name
- database username and password

#### 7.2 Clone the project's GitHub repository

1. Locate the repository here https://github.com/ruszkipista/cims03-my-car
2. Click the 'Code' dropdown above the file list
3. Copy the URL for the repository (https://github.com/ruszkipista/cims03-my-car.git)
4. Open a terminal on your computer
5. Change the current working directory where the cloned folder will be located
6. Clone the repo onto your machine with the following terminal command
'''
git clone https://github.com/ruszkipista/cims03-my-car.git
'''

#### 7.3 Create local files for environment variables
Change working directory to the cloned folder and start your code editor
```
cd cims03-my-car
code .
```
Create file `envWS.py` with the following content into the root of the project folder
```
import os
os.environ.setdefault("FLASK_SECRET_KEY", "<secret key>")
os.environ.setdefault("FLASK_IP",         "127.0.0.1")
os.environ.setdefault("PORT",             "5500")
os.environ.setdefault("FLASK_DEBUG",      "True")
```
The `<secret key>` can be any random character string from your keyboard.

Create file `envDB.py` into the root of the project folder with the following content:
```
import os
os.environ.setdefault("MONGO_CLUSTER",    "<cluster name>")
os.environ.setdefault("MONGO_DB_NAME",    "<database name>")
os.environ.setdefault("MONGO_DB_USER",    "<user name>")
os.environ.setdefault("MONGO_DB_PASS",    "<password>")
os.environ.setdefault("MONGO_INIT",       "True")
```
Take `<cluster name>`, `<username>`, `<password>` from the MongoDB creation item at 7.1

The `MONGO_INIT=True` parameter triggers the initialization of the database content, every time the application is started. To prevent that, set it to `False` so your changes in the DB are preserved between sessions. If you make a change in the DB structure, the DB content needs to be initialized or you need to do the field catalog and collection changes manually on the DB.
  
#### 7.4 Set up the Python environment
In your development environment, upgrade `pip` if needed
```
pip install --upgrade pip
```
Install `virtualenv`:
```
pip install virtualenv
```
Open a terminal in the project root directory and run:
```
virtualenv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```
#### 7.5 Start the web server:
```
python app.py
```

### Deployment on Heroku
[Heroku](https://www.heroku.com/) is a PaaS cloud service, you can deploy this project for free on it.

#### 7.6 Prerequisites:
- you forked or copied this project into your repository on GitHub.
- Heroku requires these files to deploy successfully, they are both in the root folder of the project:
- `requirements.txt`
- `Procfile`
- you already have a Heroku account, or you need to register one.

#### 7.7 Create a Heroku App
Follow these steps to deploy the app from GitHub to Heroku:
- In Heroku, Create New App, give it a platform-unique name, choose region, click on `Create App` button
- On the app/Deployment page select GitHub as Deployment method, underneath click on `Connect GitHub` button
- In the GitHub authorization popup window login into GitHub with your GitHub username and click on `Authorize Heroku` button
- Type in your repo name and click `search`. It lists your repos. Choose the one and click on `connect` next to it.
- either enable automatic deployment on every push to the chosen branch or stick to manual deployment
- go to app/Settings page, click on `Reveal Config Vars` and enter the following variables and their values from the `envWS.py` and `envDB` files:
  * FLASK_SECRET_KEY
  * MONGO_CLUSTER
  * MONGO_DB_NAME
  * MONGO_DB_PASS
  * MONGO_DB_USER
  * MONGO_INIT

The `MONGO_INIT=True` parameter triggers the initialization of the database content, be mindful when you allow this to happen.
Furthermore, if you you use the same MongoDB database as in development, the init can ruin your data on Heroku an vica versa.

## 8. Credits

### Acknowledgements
My inspiration for this project came from my own booking where I keep car related transaction data in a google spreadsheet.

The technical solution started out from the [Task Manager](https://github.com/ruszkipista/ci12-task-master) code along mini project taught in the Code Institute curriculum.

I thank [Nishant Kumar](https://github.com/nishant8BITS) for mentoring me during the project. He suggested to study [Clean Code](http://cleancoder.com/) by Uncle Bob and split up the monolith code into small functions. Despite much of my efforts, Uncle Bob still would not approve the current state of the code, there is still much to learn ...

### Media
Used 3 car images from the following places:
- Chrysler PT Cruiser https://www.nadaguides.com/Cars/2004/Chrysler/PT-Cruiser
- Toyota Yaris https://idd-katalogus.medija.hu/original/0010644.jpg
- Mazda 3 https://www.autoblog.com/buy/2008-Mazda-Mazda3-s_Sport__4dr_Hatchback/
