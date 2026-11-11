from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

OUT = 'sales_management_database_guide.docx'

tables = [
    ('customers', 'Stores customer contact details and the date each customer record was created.', [
        ('customer_id', 'BIGINT GENERATED ALWAYS AS IDENTITY', 'Unique generated identifier for a customer.', 'PRIMARY KEY'),
        ('name', 'TEXT', 'Customer full name.', 'NOT NULL'),
        ('email', 'TEXT', 'Customer email address; when provided, it must be unique.', 'UNIQUE (nullable)'),
        ('phone', 'TEXT', 'Customer phone number.', 'Nullable'),
        ('created_at', 'TIMESTAMPTZ', 'Date and time the row was created; defaults to the current time.', 'NOT NULL; DEFAULT NOW()'),
    ]),
    ('employees', 'Stores employee identity, work contact details, job title, and hire date.', [
        ('employee_id', 'BIGINT GENERATED ALWAYS AS IDENTITY', 'Unique generated identifier for an employee.', 'PRIMARY KEY'),
        ('name', 'TEXT', 'Employee full name.', 'NOT NULL'),
        ('email', 'TEXT', 'Employee email address; must be unique.', 'NOT NULL; UNIQUE'),
        ('job_title', 'TEXT', 'Employee role or job title.', 'Nullable'),
        ('hired_at', 'DATE', 'Employee hire date.', 'Nullable'),
    ]),
    ('products', 'Catalog of products available for sale, with descriptions, current prices, and stock quantities.', [
        ('product_id', 'BIGINT GENERATED ALWAYS AS IDENTITY', 'Unique generated identifier for a product.', 'PRIMARY KEY'),
        ('name', 'TEXT', 'Product name.', 'NOT NULL'),
        ('description', 'TEXT', 'Product description.', 'Nullable'),
        ('unit_price', 'NUMERIC(10, 2)', 'Current unit price, with up to 10 digits and 2 decimal places.', 'NOT NULL; CHECK >= 0'),
        ('stock_qty', 'INTEGER', 'Current stock quantity; defaults to zero.', 'NOT NULL; DEFAULT 0; CHECK >= 0'),
    ]),
    ('orders', 'One row per customer order. Links the order to its customer and, optionally, the employee handling it.', [
        ('order_id', 'BIGINT GENERATED ALWAYS AS IDENTITY', 'Unique generated identifier for an order.', 'PRIMARY KEY'),
        ('customer_id', 'BIGINT', 'Customer who placed the order; references customers.customer_id.', 'NOT NULL; FOREIGN KEY'),
        ('employee_id', 'BIGINT', 'Employee handling the order; references employees.employee_id.', 'FOREIGN KEY; nullable'),
        ('order_date', 'TIMESTAMPTZ', 'Date and time the order was created; defaults to the current time.', 'NOT NULL; DEFAULT NOW()'),
        ('status', 'TEXT', 'Order progress; defaults to pending. Allowed: pending, processing, shipped, delivered, cancelled.', 'NOT NULL; DEFAULT pending; CHECK'),
    ]),
    ('order_items', 'Line items belonging to orders. Each row identifies a product, quantity, and the unit price recorded for that order.', [
        ('order_id', 'BIGINT', 'Order containing this line; references orders.order_id and cascades on order deletion.', 'PRIMARY KEY (composite); FOREIGN KEY; ON DELETE CASCADE'),
        ('product_id', 'BIGINT', 'Product on this line; references products.product_id.', 'PRIMARY KEY (composite); FOREIGN KEY'),
        ('quantity', 'INTEGER', 'Number of product units in this line; must be greater than zero.', 'NOT NULL; CHECK > 0'),
        ('unit_price', 'NUMERIC(10, 2)', 'Price per unit recorded on this order line; must be nonnegative.', 'NOT NULL; CHECK >= 0'),
    ]),
]

doc = Document()
sec = doc.sections[0]
sec.top_margin = Inches(.62)
sec.bottom_margin = Inches(.58)
sec.left_margin = Inches(.68)
sec.right_margin = Inches(.68)
styles = doc.styles
styles['Normal'].font.name = 'Aptos'
styles['Normal'].font.size = Pt(9)
styles['Normal'].font.color.rgb = RGBColor(35, 45, 57)
styles['Normal'].paragraph_format.space_after = Pt(4)
for s in ('Title', 'Heading 1', 'Heading 2'):
    styles[s].font.name = 'Aptos Display'
    styles[s].font.color.rgb = RGBColor(0, 0, 0)
styles['Title'].font.size = Pt(24)
styles['Title'].font.bold = True
styles['Heading 1'].font.size = Pt(17)
styles['Heading 1'].font.bold = True
styles['Heading 2'].font.size = Pt(10)
styles['Heading 2'].font.bold = True

def shade(cell, fill):
    tcpr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), fill)
    tcpr.append(shd)

def set_cell_margins(cell, top=90, start=100, bottom=90, end=100):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    mar = OxmlElement('w:tcMar')
    for tag, val in [('top', top), ('start', start), ('bottom', bottom), ('end', end)]:
        node = OxmlElement('w:' + tag)
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        mar.append(node)
    tcPr.append(mar)

for idx, (name, desc, columns) in enumerate(tables):
    if idx:
        doc.add_page_break()
    if idx == 0:
        p = doc.add_paragraph(style='Title')
        p.add_run('Sales Management Database Guide')
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(8)
        r = p.add_run('Database: '); r.bold = True
        p.add_run('sales_management')
        p.add_run('    |    Schema: public    |    Engine: PostgreSQL')
        p = doc.add_paragraph('Purpose: a sample sales database for customer and employee records, product inventory, orders, and the products within each order.')
        p.paragraph_format.space_after = Pt(5)
        p = doc.add_paragraph()
        p.add_run('Read-only login: ').bold = True
        p.add_run('sales_readonly is intended to connect to this database and query permitted tables with SELECT. Database connection permission and table SELECT permission are granted separately.')
        p = doc.add_paragraph()
        p.add_run('Chunking plan: ').bold = True
        p.add_run('use one table page as one source chunk; set metadata name to the table name shown on that page. If a page chunk exceeds the chosen limit (for example, 250 tokens), split it with overlap within that page chunk.')
        p.paragraph_format.space_after = Pt(8)
    else:
        p = doc.add_paragraph()
        p.add_run('Database: sales_management    |    Schema: public').font.size = Pt(8)
    doc.add_heading(name, level=1)
    p = doc.add_paragraph(desc)
    p.paragraph_format.space_after = Pt(7)
    doc.add_heading('Columns', level=2)
    t = doc.add_table(rows=1, cols=4)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    widths = [Inches(1.25), Inches(1.8), Inches(2.75), Inches(1.3)]
    headers = ['Column name', 'Data type', 'Definition', 'Key and rules']
    for j, h in enumerate(headers):
        c = t.rows[0].cells[j]
        c.width = widths[j]
        c.text = h
        shade(c, '24476B')
    for row in columns:
        cells = t.add_row().cells
        for j, value in enumerate(row):
            cells[j].width = widths[j]
            cells[j].text = value
            if len(t.rows) % 2 == 0:
                shade(cells[j], 'F1F5F8')
    for row in t.rows:
        for c in row.cells:
            c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(c)
            for p in c.paragraphs:
                p.paragraph_format.space_after = Pt(0)
                for run in p.runs:
                    run.font.name = 'Aptos'
                    run.font.size = Pt(8)
                    if row is t.rows[0]:
                        run.font.bold = True
                        run.font.color.rgb = RGBColor(255, 255, 255)
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.add_run('Primary key: ').bold = True
    if name == 'order_items':
        p.add_run('(order_id, product_id), a composite primary key.')
    else:
        p.add_run(columns[0][0] + '.')
    if name == 'orders':
        p = doc.add_paragraph('Indexes: idx_orders_customer_id on customer_id; idx_orders_employee_id on employee_id.')
        p.paragraph_format.space_before = Pt(1)
    elif name == 'order_items':
        p = doc.add_paragraph('Relationships: many order_items belong to one order and reference one product. The product price is stored on the line for order history.')
        p.paragraph_format.space_before = Pt(1)

doc.core_properties.title = 'Sales Management Database Guide'
doc.core_properties.subject = 'PostgreSQL database and table documentation for sales_management'
doc.save(OUT)
print(OUT)
