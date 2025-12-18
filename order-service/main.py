from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict
from datetime import datetime
import logging
import random
import threading

# ----------------------------
# Azure Application Insights logging setup
# ----------------------------
from opencensus.ext.azure.log_exporter import AzureLogHandler

# IMPORTANT: paste your real Instrumentation Key between the quotes
INSTRUMENTATION_KEY = "945c92c3-9d31-48af-b860-7f52a37e7e79"

# Create logger
logger = logging.getLogger("order-service")
logger.setLevel(logging.INFO)

# Console handler (shows logs in your terminal)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# Azure handler (sends logs to Application Insights)
if INSTRUMENTATION_KEY:
    azure_handler = AzureLogHandler(
        connection_string=f"InstrumentationKey={INSTRUMENTATION_KEY}"
    )
    azure_handler.setLevel(logging.INFO)
    azure_handler.setFormatter(console_formatter)

    # FIX for Python 3.13: give the handler a lock
    azure_handler.lock = threading.RLock()

    logger.addHandler(azure_handler)
    logger.info("Azure Application Insights logging is ENABLED")
else:
    logger.warning("Azure Instrumentation Key not set. Cloud logging is DISABLED")
# ----------------------------
# FastAPI app
# ----------------------------
app = FastAPI(
    title="Order Service API",
    description="Order Service for Smart Logistics project",
    version="0.3.0"
)

# ----------------------------
# Data Models
# ----------------------------

class OrderCreate(BaseModel):
    customer_name: str
    product_id: str
    quantity: int
    delivery_address: str

class Order(BaseModel):
    order_id: str
    customer_name: str
    product_id: str
    quantity: int
    delivery_address: str
    status: str
    created_at: str

# ----------------------------
# In-memory "database"
# ----------------------------

orders_db: Dict[str, Order] = {}


# ----------------------------
# Basic Endpoints
# ----------------------------

@app.get("/")
def root():
    logger.info("Root endpoint called")
    return {"message": "Order Service is running"}


@app.get("/health")
def health():
    logger.info("Health check called")
    return {"status": "healthy", "service": "order-service"}


# ----------------------------
# Simple Order Endpoints
# ----------------------------

@app.post("/orders", response_model=Order)
def create_order(order_data: OrderCreate):
    """
    Simple order creation (no external checks).
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    order_id = f"ORD-{timestamp}"

    logger.info(
        "Creating simple order %s for customer=%s, product=%s, quantity=%s",
        order_id, order_data.customer_name, order_data.product_id, order_data.quantity
    )

    new_order = Order(
        order_id=order_id,
        customer_name=order_data.customer_name,
        product_id=order_data.product_id,
        quantity=order_data.quantity,
        delivery_address=order_data.delivery_address,
        status="CREATED",
        created_at=datetime.now().isoformat()
    )

    orders_db[order_id] = new_order
    return new_order


@app.get("/orders/{order_id}", response_model=Order)
def get_order(order_id: str):
    """
    Get a single order by ID.
    """
    if order_id not in orders_db:
        logger.warning("Order %s not found", order_id)
        raise HTTPException(status_code=404, detail="Order not found")

    logger.info("Returning order %s", order_id)
    return orders_db[order_id]


@app.get("/orders")
def list_orders():
    """
    List all orders.
    """
    logger.info("Listing all orders, total=%s", len(orders_db))
    return {
        "total": len(orders_db),
        "orders": list(orders_db.values())
    }


# ----------------------------
# Simulated External Services
# ----------------------------

def simulate_inventory_check(product_id: str, quantity: int):
    """
    Simulate calling an Inventory Service.
    Sometimes fails to mimic real-world issues.
    """
    logger.info("Checking inventory for product=%s quantity=%s", product_id, quantity)

    r = random.random()

    # 20% chance: inventory service down
    if r < 0.2:
        logger.error("Inventory service unavailable for product=%s", product_id)
        raise HTTPException(status_code=503, detail="Inventory service unavailable")

    # next 10% (0.2 to 0.3): insufficient stock
    if r < 0.3:
        logger.warning("Insufficient stock for product=%s", product_id)
        raise HTTPException(status_code=400, detail="Insufficient stock")

    # else: success
    logger.info("Inventory OK for product=%s", product_id)
    return {"available": True, "quantity": quantity}


def simulate_courier_assignment(order_id: str, address: str):
    """
    Simulate calling a Courier/Fleet API.
    Sometimes fails with timeout.
    """
    logger.info("Assigning courier for order=%s to address=%s", order_id, address)

    r = random.random()

    # 15% chance: courier API timeout
    if r < 0.15:
        logger.error("Courier API timeout for order=%s", order_id)
        raise HTTPException(status_code=504, detail="Courier service timeout")

    courier_id = f"COURIER-{random.randint(100, 999)}"
    logger.info("Courier %s assigned to order %s", courier_id, order_id)

    return {"courier_id": courier_id, "status": "assigned"}


# ----------------------------
# Advanced Order Endpoint (with failures)
# ----------------------------

@app.post("/orders/process", response_model=Order)
def process_order(order_data: OrderCreate):
    """
    Create an order AND:
    - Check inventory
    - Assign courier

    This endpoint will sometimes fail to simulate:
    - Inventory service down
    - Insufficient stock
    - Courier timeout
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    order_id = f"ORD-PROC-{timestamp}"

    logger.info(
        "Processing order %s for customer=%s, product=%s, quantity=%s",
        order_id, order_data.customer_name, order_data.product_id, order_data.quantity
    )

    try:
        # Step 1: Inventory
        simulate_inventory_check(order_data.product_id, order_data.quantity)

        # Step 2: Courier
        simulate_courier_assignment(order_id, order_data.delivery_address)

        # If both succeed, mark as CONFIRMED
        new_order = Order(
            order_id=order_id,
            customer_name=order_data.customer_name,
            product_id=order_data.product_id,
            quantity=order_data.quantity,
            delivery_address=order_data.delivery_address,
            status="CONFIRMED",
            created_at=datetime.now().isoformat()
        )

        orders_db[order_id] = new_order

        logger.info("Order %s processed successfully (CONFIRMED)", order_id)
        return new_order

    except HTTPException as e:
        logger.error(
            "Order %s failed during processing: status=%s detail=%s",
            order_id, e.status_code, e.detail
        )
        raise