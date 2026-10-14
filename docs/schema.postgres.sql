-- Generado por python -m scripts.export_ddl. No editar a mano.

CREATE TABLE customer_tiers (
	tier VARCHAR(1) NOT NULL, 
	max_discount_pct NUMERIC(5, 2) NOT NULL, 
	margin_pct NUMERIC(5, 2) NOT NULL, 
	credit_days INTEGER NOT NULL, 
	PRIMARY KEY (tier)
);

CREATE TABLE products (
	code VARCHAR(20) NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	alias VARCHAR(60), 
	category_code VARCHAR(3) NOT NULL, 
	unit_code VARCHAR(3) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	prefix VARCHAR(3) NOT NULL, 
	is_core_product BOOLEAN NOT NULL, 
	PRIMARY KEY (code)
);

CREATE INDEX ix_products_is_core_product ON products (is_core_product);

CREATE TABLE salespeople (
	code VARCHAR(3) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	location VARCHAR(80), 
	is_active BOOLEAN NOT NULL, 
	PRIMARY KEY (code)
);

CREATE TABLE stock_balances (
	warehouse_code VARCHAR(3) NOT NULL, 
	year INTEGER NOT NULL, 
	month INTEGER NOT NULL, 
	product_code VARCHAR(20) NOT NULL, 
	product_name VARCHAR(150), 
	balance NUMERIC(14, 4) NOT NULL, 
	period_end DATE NOT NULL, 
	PRIMARY KEY (warehouse_code, year, month, product_code)
);

CREATE INDEX ix_stock_balances_period_end ON stock_balances (period_end);

CREATE TABLE customers (
	ruc VARCHAR(15) NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	address VARCHAR(200), 
	phone VARCHAR(40), 
	email VARCHAR(120), 
	salesperson_code VARCHAR(3) NOT NULL, 
	department_code VARCHAR(3), 
	department VARCHAR(60), 
	segment_code VARCHAR(3), 
	condition_code VARCHAR(3), 
	is_active BOOLEAN NOT NULL, 
	tax_id_kind VARCHAR(10) NOT NULL, 
	PRIMARY KEY (ruc), 
	FOREIGN KEY(salesperson_code) REFERENCES salespeople (code)
);

CREATE INDEX ix_customers_salesperson_code ON customers (salesperson_code);

CREATE TABLE users (
	id SERIAL NOT NULL, 
	email VARCHAR(200) NOT NULL, 
	password_hash VARCHAR(300) NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	sales_rep_code VARCHAR(3), 
	active BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(sales_rep_code) REFERENCES salespeople (code)
);

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE TABLE contacts (
	id SERIAL NOT NULL, 
	ruc VARCHAR(15) NOT NULL, 
	user_id INTEGER NOT NULL, 
	outcome VARCHAR(30) NOT NULL, 
	contact_date DATE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(ruc) REFERENCES customers (ruc), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_contacts_ruc ON contacts (ruc);

CREATE TABLE customer_rebates (
	ruc VARCHAR(15) NOT NULL, 
	rebate_pct NUMERIC(5, 2) NOT NULL, 
	PRIMARY KEY (ruc), 
	FOREIGN KEY(ruc) REFERENCES customers (ruc)
);

CREATE TABLE orders (
	order_no VARCHAR(20) NOT NULL, 
	order_date DATE NOT NULL, 
	ruc VARCHAR(15) NOT NULL, 
	salesperson_code VARCHAR(3) NOT NULL, 
	channel_code VARCHAR(3) NOT NULL, 
	subtotal NUMERIC(14, 2) NOT NULL, 
	discount NUMERIC(14, 2) NOT NULL, 
	tax NUMERIC(14, 2) NOT NULL, 
	total NUMERIC(14, 2) NOT NULL, 
	status_code VARCHAR(1), 
	is_dispatched BOOLEAN NOT NULL, 
	PRIMARY KEY (order_no), 
	FOREIGN KEY(ruc) REFERENCES customers (ruc), 
	FOREIGN KEY(salesperson_code) REFERENCES salespeople (code)
);

CREATE INDEX ix_orders_order_date ON orders (order_date);

CREATE INDEX ix_orders_ruc ON orders (ruc);

CREATE INDEX ix_orders_salesperson_code ON orders (salesperson_code);

CREATE TABLE quotes (
	id SERIAL NOT NULL, 
	ruc VARCHAR(15) NOT NULL, 
	user_id INTEGER NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	discount_pct NUMERIC(5, 2) NOT NULL, 
	total NUMERIC(14, 2) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(ruc) REFERENCES customers (ruc), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_quotes_ruc ON quotes (ruc);

CREATE TABLE receipts (
	receipt_no VARCHAR(20) NOT NULL, 
	document_no VARCHAR(20) NOT NULL, 
	receipt_date DATE NOT NULL, 
	ruc VARCHAR(15) NOT NULL, 
	type_code VARCHAR(3) NOT NULL, 
	code_c6 VARCHAR(3) NOT NULL, 
	payment_method_code VARCHAR(3) NOT NULL, 
	code_c8 VARCHAR(3) NOT NULL, 
	reference_no VARCHAR(30), 
	amount NUMERIC(14, 2) NOT NULL, 
	applied_date DATE NOT NULL, 
	PRIMARY KEY (receipt_no, document_no), 
	FOREIGN KEY(ruc) REFERENCES customers (ruc)
);

CREATE INDEX ix_receipts_receipt_date ON receipts (receipt_date);

CREATE INDEX ix_receipts_ruc ON receipts (ruc);

CREATE TABLE order_lines (
	id SERIAL NOT NULL, 
	order_no VARCHAR(20) NOT NULL, 
	line_no INTEGER NOT NULL, 
	dup_seq INTEGER NOT NULL, 
	product_code VARCHAR(20) NOT NULL, 
	unit_code VARCHAR(3) NOT NULL, 
	quantity NUMERIC(14, 4) NOT NULL, 
	quantity_dispatched NUMERIC(14, 4) NOT NULL, 
	unit_price NUMERIC(18, 10) NOT NULL, 
	discount_pct NUMERIC(5, 2) NOT NULL, 
	line_total NUMERIC(14, 2) NOT NULL, 
	is_bonus BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_order_lines_order_line_seq UNIQUE (order_no, line_no, dup_seq), 
	FOREIGN KEY(order_no) REFERENCES orders (order_no), 
	FOREIGN KEY(product_code) REFERENCES products (code)
);

CREATE INDEX ix_order_lines_order_no ON order_lines (order_no);

CREATE INDEX ix_order_lines_product_code ON order_lines (product_code);

CREATE TABLE quote_lines (
	quote_id INTEGER NOT NULL, 
	product_code VARCHAR(20) NOT NULL, 
	quantity NUMERIC(12, 2) NOT NULL, 
	unit_price NUMERIC(14, 2) NOT NULL, 
	PRIMARY KEY (quote_id, product_code), 
	FOREIGN KEY(quote_id) REFERENCES quotes (id), 
	FOREIGN KEY(product_code) REFERENCES products (code)
);
