from faker import Faker
import pandas as pd

fake = Faker()

NUM_CUSTOMERS = 10_000
NUM_PRODUCTS = 2_000
NUM_ORDERS = 50_000


def generate_customers():
    customers = []

    for i in range(NUM_CUSTOMERS):
        customers.append({
            "customer_id": f"CUST{i + 1:06d}",
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "email": fake.email(),
            "phone": fake.phone_number(),
            "city": fake.city(),
            "state": fake.state(),
            "country": "India",
            "created_at": fake.date_time_this_year()
        })

    return pd.DataFrame(customers)


def generate_products():
    products = []

    categories = [
        "Electronics",
        "Fashion",
        "Home",
        "Beauty",
        "Sports"
    ]

    for i in range(NUM_PRODUCTS):
        products.append({
            "product_id": f"PROD{i + 1:06d}",
            "product_name": fake.catch_phrase(),
            "category": fake.random_element(categories),
            "brand": fake.company(),
            "price": round(fake.random_number(digits=4) + fake.random.random(), 2),
            "cost": round(fake.random_number(digits=3) + fake.random.random(), 2),
            "created_at": fake.date_time_this_year()
        })

    return pd.DataFrame(products)


def generate_orders(customers):
    orders = []

    order_statuses = [
        "PLACED",
        "CONFIRMED",
        "SHIPPED",
        "DELIVERED",
        "CANCELLED",
        "RETURNED"
    ]

    for i in range(NUM_ORDERS):
        customer_id = fake.random_element(customers["customer_id"].tolist())

        orders.append({
            "order_id": f"ORD{i + 1:07d}",
            "customer_id": customer_id,
            "order_date": fake.date_time_this_year(),
            "order_status": fake.random_element(order_statuses),
"total_amount": 0.0
        })

    return pd.DataFrame(orders)


def generate_order_items(orders, products):
    order_items = []

    order_item_id = 1

    for _, order in orders.iterrows():

        number_of_items = fake.random_int(min=1, max=5)

        selected_products = products.sample(
            n=number_of_items,
            replace=False
        )

        total_amount = 0

        for _, product in selected_products.iterrows():

            quantity = fake.random_int(min=1, max=3)
            unit_price = product["price"]

            item_total = quantity * unit_price
            total_amount += item_total

            order_items.append({
                "order_item_id": f"ITEM{order_item_id:08d}",
                "order_id": order["order_id"],
                "product_id": product["product_id"],
                "quantity": quantity,
                "unit_price": unit_price
            })

            order_item_id += 1

        orders.loc[
            orders["order_id"] == order["order_id"],
            "total_amount"
        ] = round(total_amount, 2)

    return pd.DataFrame(order_items)

def generate_payments(orders):
    payments = []

    payment_methods = [
        "UPI",
        "CREDIT_CARD",
        "DEBIT_CARD",
        "NET_BANKING",
        "COD"
    ]

    payment_statuses = [
        "SUCCESS",
        "FAILED",
        "REFUNDED"
    ]

    for i, (_, order) in enumerate(orders.iterrows()):

        payments.append({
            "payment_id": f"PAY{i + 1:07d}",
            "order_id": order["order_id"],
            "payment_method": fake.random_element(payment_methods),
            "payment_status": fake.random_element(payment_statuses),
            "amount": order["total_amount"],
            "payment_timestamp": order["order_date"]
        })

    return pd.DataFrame(payments)


def generate_shipments(orders):
    shipments = []

    shipment_statuses = [
        "PROCESSING",
        "SHIPPED",
        "IN_TRANSIT",
        "DELIVERED",
        "RETURNED"
    ]

    warehouses = [
        "WH_MUMBAI",
        "WH_DELHI",
        "WH_BANGALORE",
        "WH_HYDERABAD"
    ]

    for i, (_, order) in enumerate(orders.iterrows()):

        shipments.append({
            "shipment_id": f"SHIP{i + 1:07d}",
            "order_id": order["order_id"],
            "warehouse_id": fake.random_element(warehouses),
            "shipment_status": fake.random_element(shipment_statuses),
            "shipped_at": fake.date_time_this_year(),
            "delivered_at": fake.date_time_this_year()
        })

    return pd.DataFrame(shipments)


def generate_inventory(products):
    inventory = []

    warehouses = [
        "WH_MUMBAI",
        "WH_DELHI",
        "WH_BANGALORE",
        "WH_HYDERABAD"
    ]

    inventory_id = 1

    for _, product in products.iterrows():

        for warehouse in warehouses:

            inventory.append({
                "inventory_id": f"INV{inventory_id:07d}",
                "product_id": product["product_id"],
                "warehouse_id": warehouse,
                "quantity": fake.random_int(min=0, max=1000),
                "updated_at": fake.date_time_this_year()
            })

            inventory_id += 1

    return pd.DataFrame(inventory)

def main():
    customers = generate_customers()
    products = generate_products()

    orders = generate_orders(customers)
    order_items = generate_order_items(orders, products)

    payments = generate_payments(orders)
    shipments = generate_shipments(orders)
    inventory = generate_inventory(products)

    customers.to_csv(
        "data/generated/customers.csv",
        index=False
    )

    products.to_csv(
        "data/generated/products.csv",
        index=False
    )

    orders.to_csv(
        "data/generated/orders.csv",
        index=False
    )

    order_items.to_csv(
        "data/generated/order_items.csv",
        index=False
    )

    payments.to_csv(
        "data/generated/payments.csv",
        index=False
    )

    shipments.to_csv(
        "data/generated/shipments.csv",
        index=False
    )

    inventory.to_csv(
        "data/generated/inventory.csv",
        index=False
    )

    print(f"Generated {len(customers)} customers")
    print(f"Generated {len(products)} products")
    print(f"Generated {len(orders)} orders")
    print(f"Generated {len(order_items)} order items")
    print(f"Generated {len(payments)} payments")
    print(f"Generated {len(shipments)} shipments")
    print(f"Generated {len(inventory)} inventory records")


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()

