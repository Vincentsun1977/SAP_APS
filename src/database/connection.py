"""
Supabase database connection and operations
"""
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    Client = None

from typing import Optional


class SupabaseDB:
    """Supabase database client wrapper"""
    
    def __init__(self):
        if not SUPABASE_AVAILABLE:
            self.client = None
            self.service_client = None
            return
        
        try:
            from config import get_settings
            settings = get_settings()
            self.client: Client = create_client(
                settings.supabase_url,
                settings.supabase_key
            )
            self.service_client: Client = create_client(
                settings.supabase_url,
                settings.supabase_service_key
            )
        except Exception:
            self.client = None
            self.service_client = None
    
    def insert_orders(self, orders: list[dict]) -> dict:
        """Insert production orders into database"""
        response = self.client.table("raw_orders").insert(orders).execute()
        return response.data
    
    def get_orders(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """Retrieve production orders"""
        response = self.client.table("raw_orders") \
            .select("*") \
            .range(offset, offset + limit - 1) \
            .execute()
        return response.data
    
    def insert_features(self, features: list[dict]) -> dict:
        """Insert engineered features"""
        response = self.client.table("features").insert(features).execute()
        return response.data
    
    def insert_predictions(self, predictions: list[dict]) -> dict:
        """Insert model predictions"""
        response = self.client.table("predictions").insert(predictions).execute()
        return response.data
    
    def get_latest_model(self) -> Optional[dict]:
        """Get the latest active model metadata"""
        response = self.client.table("model_metadata") \
            .select("*") \
            .eq("is_active", True) \
            .order("training_date", desc=True) \
            .limit(1) \
            .execute()
        
        return response.data[0] if response.data else None
    
    def save_model_metadata(self, metadata: dict) -> dict:
        """Save model training metadata"""
        if self.client is None:
            raise Exception("Supabase not available")
        response = self.client.table("model_metadata").insert(metadata).execute()
        return response.data


# Global instance
db = SupabaseDB()
