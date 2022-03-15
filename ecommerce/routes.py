import os
import secrets
import Image
from flask import render_template, request
from ecommerce import app
from ecommerce.forms import *
from plotly.offline import plot
import plotly.graph_objs as go
from flask import Markup
from ecommerce.models import *


@app.route("/login", methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if is_valid(email, password):
            session['email'] = email
            if isUserAdmin():
                # Return to admin page
                return redirect('admin')
            return redirect(url_for('root'))
        else:
            error = 'Invalid UserId / Password'
            return render_template('index.html', error=error)


@app.route("/logout")
def logout():
    session.pop('email', None)
    return redirect(url_for('root'))


@app.route("/registerationForm")
def registrationForm():
    return render_template("register.html")


@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Parse form data
        msg = extractAndPersistUserDataFromForm(request)
        if msg:
            return render_template('index.html', error=msg)
        else:
            return render_template('index.html', error="Registration failed")


@app.route("/")
@app.route("/home")
def root():
    loggedIn, firstName, productCountinKartForGivenUser = getLoginUserDetails()
    allProductDetails = getAllProducts()
    print(allProductDetails)
    allProductsMassagedDetails = massageItemData(allProductDetails)
    categoryData = getCategoryDetails()

    return render_template('index.html', itemData=allProductsMassagedDetails, loggedIn=loggedIn, firstName=firstName,
                           productCountinKartForGivenUser=productCountinKartForGivenUser,
                           categoryData=categoryData)


@app.route("/displayCategory")
def displayCategory():
    loggedIn, firstName, noOfItems = getLoginUserDetails()
    categoryId = request.args.get("categoryId")

    productDetailsByCategoryId = Product.query.join(ProductCategory, Product.productid == ProductCategory.productid) \
        .add_columns(Product.productid, Product.product_name, Product.regular_price, Product.discounted_price,
                     Product.image) \
        .join(Category, Category.categoryid == ProductCategory.categoryid) \
        .filter(Category.categoryid == int(categoryId)) \
        .add_columns(Category.category_name) \
        .all()

    categoryName = productDetailsByCategoryId[0].category_name
    data = massageItemData(productDetailsByCategoryId)
    return render_template('displayCategory.html', data=data, loggedIn=loggedIn, firstName=firstName,
                           noOfItems=noOfItems, categoryName=categoryName)


@app.route("/productDescription")
def productDescription():
    loggedIn, firstName, noOfItems = getLoginUserDetails()
    productid = request.args.get('productId')
    productDetailsByProductId = getProductDetails(productid)
    return render_template("productDescription.html", data=productDetailsByProductId, loggedIn=loggedIn,
                           firstName=firstName,
                           noOfItems=noOfItems)


@app.route("/addToCart",  methods=['GET', 'POST'])
def addToCart():
    if isUserLoggedIn():
        product_details = request.form['weight']
        sku = product_details.split(" - ")[0]
        subproductId = product_details.split(" - ")[1]
        # Using Flask-SQLAlchmy SubQuery
        extractAndPersistKartDetailsUsingSubquery(sku,subproductId)
        # Using Flask-SQLAlchmy normal query
        # extractAndPersistKartDetailsUsingkwargs(productId)
        flash('Item successfully added to cart !!', 'success')
        return redirect(url_for('root'))
    else:
        # flash('please log in !!', 'success')
        return redirect(url_for('loginForm'))


@app.route("/cart")
def cart():
    if isUserLoggedIn():
        loggedIn, firstName, productCountinKartForGivenUser = getLoginUserDetails()
        cartdetails, totalsum, tax = getusercartdetails();
        return render_template("cart.html", cartData=cartdetails,
                               productCountinKartForGivenUser=productCountinKartForGivenUser, loggedIn=loggedIn,
                               firstName=firstName, totalsum=totalsum, tax=tax)
    else:
        return redirect(url_for('root'))

@app.route("/admin/category/<int:category_id>", methods=['GET'])
def category(category_id):
    if isUserAdmin():
        category = Category.query.get_or_404(category_id)
        return render_template('adminCategory.html', category=category)
    return redirect(url_for('root'))

@app.route("/admin/categories/new", methods=['GET', 'POST'])
def addCategory():
    if isUserAdmin():
        form = addCategoryForm()
        if form.validate_on_submit():
            category = Category(category_name=form.category_name.data)
            db.session.add(category)
            db.session.commit()
            flash(f'Category {form.category_name.data}! added successfully', 'success')
            return redirect(url_for('getCategories'))
        return render_template("addCategory.html", form=form)
    return redirect(url_for('getCategories'))


@app.route("/admin/categories/<int:category_id>/update", methods=['GET', 'POST'])
def update_category(category_id):
    if isUserAdmin():
        category = Category.query.get_or_404(category_id)
        form = addCategoryForm()
        if form.validate_on_submit():
            category.category_name= form.category_name.data
            db.session.commit()
            flash('This category has been updated!', 'success')
            return redirect(url_for('getCategories'))
        elif request.method == 'GET':
            form.category_name.data = category.category_name
        return render_template('addCategory.html', legend="Update Category", form=form)
    return redirect(url_for('getCategories'))


@app.route("/admin/category/<int:category_id>/delete", methods=['POST'])
def delete_category(category_id):
    if isUserAdmin():
        ProductCategory.query.filter_by(categoryid=category_id).delete()
        db.session.commit()
        category= Category.query.get_or_404(category_id)
        db.session.delete(category)
        db.session.commit()
        flash('Your category has been deleted!', 'success')
    return redirect(url_for('getCategories'))

@app.route("/admin/categories", methods=['GET'])
def getCategories():
    if isUserAdmin():
        #categories = Category.query.all()
        cur = mysql.connection.cursor()
        #Query for number of products on a category:
        cur.execute('SELECT category.categoryid, category.category_name, COUNT(product_category.productid) as noOfProducts FROM category LEFT JOIN product_category ON category.categoryid = product_category.categoryid GROUP BY category.categoryid');
        categories = cur.fetchall()
        return render_template('adminCategories.html', categories = categories)
    return redirect(url_for('root'))


#this method is copied from Schafer's tutorials
def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/uploads', picture_fn)

    output_size = (250, 250)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)

    return picture_fn


@app.route("/admin", methods=['GET'])
def admin():
    return render_template('admin.html')

@app.route("/admin/products", methods=['GET'])
def getProducts():
    if isUserAdmin():
        products = Product.query.all()
        return render_template('adminProducts.html', products=products)
    return redirect(url_for('root'))

@app.route("/admin/products/new", methods=['GET', 'POST'])
def addProduct():
    if isUserAdmin():
        form = addProductForm()
        form.category.choices = [(row.categoryid, row.category_name) for row in Category.query.all()]
        product_icon = "" #safer way in case the image is not included in the form
        if form.validate_on_submit():
            if form.image.data:
                product_icon = save_picture(form.image.data)
            product = Product(sku=form.sku.data, product_name=form.productName.data, description=form.productDescription.data, image=product_icon, quantity=form.productQuantity.data, discounted_price=15, product_rating=0, product_review=" ", regular_price=form.productPrice.data)

            db.session.add(product)
            db.session.commit()
            product_category = ProductCategory(categoryid=form.category.data, productid=product.productid)
            db.session.add(product_category)
            db.session.commit()
            flash(f'Product {form.productName} added successfully', 'success')
            return redirect(url_for('root'))
        return render_template("addProduct.html", form=form, legend="New Product")
    return redirect(url_for('root'))


@app.route("/admin/product/<int:product_id>", methods=['GET'])
def product(product_id):
    if isUserAdmin():
        product = Product.query.get_or_404(product_id)
        return render_template('adminProduct.html', product=product)
    return redirect(url_for('root'))
  
@app.route("/admin/product/<int:product_id>/update", methods=['GET', 'POST'])
def update_product(product_id):
    if isUserAdmin():
        product = Product.query.get_or_404(product_id)
        form = addProductForm()
        form.category.choices = [(row.categoryid, row.category_name) for row in Category.query.all()]
        if form.validate_on_submit():
            if form.image.data:
                product.image = save_picture(form.image.data)
            product.product_name = form.productName.data
            product.sku = form.sku.data
            product.productDescription = form.productDescription.data
            product.stock = form.productQuantity.data
            # product.discounted_price = form.data.discounted_price = 15
            product.regular_price = form.productPrice.data
            db.session.commit()
            product_category = ProductCategory.query.filter_by(productid = product.productid).first()
            if form.category.data != product_category.categoryid:
                new_product_category = ProductCategory(categoryid=form.category.data, productid = product.productid)
                db.session.add(new_product_category)
                db.session.commit()
                db.session.delete(product_category)
                db.session.commit()

            flash('This product has been updated!', 'success')
            return redirect(url_for('getProducts'))
        elif request.method == 'GET':
            form.productName.data = product.product_name
            form.sku.data = product.sku
            form.productDescription.data = product.description
            form.productPrice.data = product.regular_price
            form.productQuantity.data = product.stock
        return render_template('addProduct.html', legend="Update Product", form=form)
    return redirect(url_for('root'))

@app.route("/admin/product/<int:product_id>/delete", methods=['POST'])
def delete_product(product_id):
    if isUserAdmin():
        product_category = ProductCategory.query.filter_by(productid=product_id).first()
        if product_category is not None:
            db.session.delete(product_category)
            db.session.commit()
        Cart.query.filter_by(productid=product_id).delete()
        db.session.commit()
        product = Product.query.get_or_404(product_id)
        db.session.delete(product)
        db.session.commit()
        flash('Your product has been deleted!', 'success')
    return redirect(url_for('getProducts'))


@app.route("/admin/users", methods=['GET'])
def getUsers():
    if isUserAdmin():
        # users = User.query.all()
        print('in')
        cur = mysql.connection.cursor()
        cur.execute('SELECT u.fname, u.lname, u.email, u.active, u.city, u.state, COUNT(o.orderid) as noOfOrders FROM `user` u LEFT JOIN `order` o ON u.userid = o.userid GROUP BY u.userid')
        users = cur.fetchall()
        return render_template('adminUsers.html', users= users)
    return redirect(url_for('root'))


@app.route("/removeFromCart")
def removeFromCart():
    if isUserLoggedIn():
        productId = int(request.args.get('productId'))
        removeProductFromCart(productId)
        return redirect(url_for('cart'))
    else:
        return redirect(url_for('loginForm'))


@app.route("/checkoutPage")
def checkoutForm():
    if isUserLoggedIn():
        cartdetails, totalsum, tax = getusercartdetails()
        return render_template("checkoutPage.html", cartData=cartdetails, totalsum=totalsum, tax=tax)
    else:
        return redirect(url_for('loginForm'))


@app.route("/createOrder", methods=['GET', 'POST'])
def createOrder():
    totalsum = request.args.get('total')
    email, username, ordernumber, address, fullname, phonenumber, provider = extractOrderdetails(request, totalsum)
    if email:
        sendEmailconfirmation(email, username, ordernumber, phonenumber, provider)

    return render_template("OrderPage.html", email=email, username=username, ordernumber=ordernumber,
                                   address=address, fullname=fullname, phonenumber=phonenumber)


@app.route("/seeTrends", methods=['GET', 'POST'])
def seeTrends():
    trendtype = str(request.args.get('trend'))
    cur = mysql.connection.cursor()
    if(trendtype=="least"):
        cur.execute("SELECT ordered_details.productid, sum(ordered_details.quantity) AS TotalQuantity,product.product_name FROM \
                       ordered_details,product where ordered_details.productid=product.productid GROUP BY productid \
                           ORDER BY TotalQuantity ASC LIMIT 3 ")
    else:
        trendtype="most"
        cur.execute("SELECT ordered_details.productid, sum(ordered_details.quantity) AS TotalQuantity,product.product_name FROM \
                ordered_details,product where ordered_details.productid=product.productid GROUP BY productid \
                    ORDER BY TotalQuantity DESC LIMIT 3 ")

    products = cur.fetchall()
    cur.close()
    x = []
    y = []
    for item in products:
        x.append(item['product_name'])
        y.append(item['TotalQuantity'])

    my_plot_div = plot([go.Bar(x=x, y=y)], output_type='div')

    return render_template('trends.html',
                           div_placeholder=Markup(my_plot_div),trendtype=trendtype
                           )