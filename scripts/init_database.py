"""
Initialize Supabase database tables
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase import create_client
from config import get_settings
from loguru import logger


# SQL for creating tables
CREATE_TABLES_SQL = """
-- 1. Raw Orders Table
CREATE TABLE IF NOT EXISTS raw_orders (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(50) UNIQUE NOT NULL,
    material_id VARCHAR(50),
    plant VARCHAR(10),
    order_type VARCHAR(20),
    planned_start TIMESTAMP,
    planned_finish TIMESTAMP,
    actual_finish TIMESTAMP,
    planned_qty DECIMAL(15,3),
    confirmed_qty DECIMAL(15,3),
    status VARCHAR(20),
    priority INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 2. Features Table
CREATE TABLE IF NOT EXISTS features (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(50) REFERENCES raw_orders(order_id),
    feature_vector JSONB,
    feature_version VARCHAR(10),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 3. Predictions Table
CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(50) REFERENCES raw_orders(order_id),
    prediction_class INTEGER,
    prediction_proba DECIMAL(5,4),
    model_version VARCHAR(20),
    predicted_at TIMESTAMP DEFAULT NOW(),
    actual_result INTEGER,
    is_correct BOOLEAN
);

-- 4. Model Metadata Table
CREATE TABLE IF NOT EXISTS model_metadata (
    id SERIAL PRIMARY KEY,
    model_version VARCHAR(20) UNIQUE,
    algorithm VARCHAR(50),
    training_date TIMESTAMP,
    train_samples INTEGER,
    test_accuracy DECIMAL(5,4),
    precision_score DECIMAL(5,4),
    recall_score DECIMAL(5,4),
    f1_score DECIMAL(5,4),
    feature_importance JSONB,
    hyperparameters JSONB,
    model_path VARCHAR(255),
    is_active BOOLEAN DEFAULT FALSE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_orders_material_id ON raw_orders(material_id);
CREATE INDEX IF NOT EXISTS idx_orders_plant ON raw_orders(plant);
CREATE INDEX IF NOT EXISTS idx_orders_status ON raw_orders(status);
CREATE INDEX IF NOT EXISTS idx_predictions_order_id ON predictions(order_id);
CREATE INDEX IF NOT EXISTS idx_model_active ON model_metadata(is_active);
"""


def init_database():
    """Initialize database tables in Supabase"""
    
    logger.info("Initializing Supabase database...")
    
    settings = get_settings()
    
    # Use service role key for admin operations
    supabase = create_client(
        settings.supabase_url,
        settings.supabase_service_key
    )
    
    # Execute SQL via Supabase SQL Editor API or use direct PostgreSQL connection
    # Note: Supabase Python client doesn't support raw SQL execution directly
    # You'll need to run these SQL commands via Supabase Dashboard > SQL Editor
    
    logger.info("\\n" + "="*60)
    logger.info("Please execute the following SQL in Supabase Dashboard:")
    logger.info("="*60)
    print(CREATE_TABLES_SQL)
    logger.info("="*60)
    logger.info("\\nGo to: https://supabase.com > Your Project > SQL Editor")
    logger.info("Paste the SQL above and click 'Run'")
    logger.info("="*60)


if __name__ == "__main__":
    init_database()
