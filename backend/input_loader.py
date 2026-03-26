# input_loader.py
"""
Input Adapter: Unified loader for all data sources
--------------------------------------------------
Supports:
1. JSON file (prototype default)
2. Natural language text (Stage 0 parser)
3. OCR output (future: Tesseract/Google Vision)

Returns: List[Dict] in unified transaction schema
"""

import json
import os
from typing import List, Dict, Union, Optional
from datetime import datetime

# Optional: Import Stage 0 parser if available
try:
    from text_parser import parse_text_to_transaction
    HAS_NLP_PARSER = True
except ImportError:
    HAS_NLP_PARSER = False
    print("⚠️ NLP parser not available. Text input will use fallback.")

class InputLoader:
    """Unified input adapter for FlowGuard"""
    
    @staticmethod
    def from_json(filepath: str) -> List[Dict]:
        """Load from fixed JSON file (prototype default)"""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Data file not found: {filepath}")
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Ensure list format
        if isinstance(data, dict):
            data = [data]
        
        # Normalize date strings → date objects
        for txn in data:
            if isinstance(txn.get('due_date'), str):
                try:
                    txn['due_date'] = datetime.strptime(txn['due_date'], "%Y-%m-%d").date()
                except:
                    pass  # Keep as string, solver handles it
        
        print(f"📦 Loaded {len(data)} transactions from {filepath}")
        return data

    @staticmethod
    def from_text(text: str, use_llm: bool = True) -> Optional[Dict]:
        """Parse natural language → transaction (Stage 0)"""
        if not HAS_NLP_PARSER and use_llm:
            print("⚠️ NLP parser not installed. Using simple fallback.")
            return InputLoader._fallback_text_parse(text)
        
        if HAS_NLP_PARSER and use_llm:
            result = parse_text_to_transaction(text)
            if result:
                # Normalize date
                if isinstance(result.get('due_date'), str):
                    try:
                        result['due_date'] = datetime.strptime(result['due_date'], "%Y-%m-%d").date()
                    except:
                        pass
                return result
        
        return InputLoader._fallback_text_parse(text)

    @staticmethod
    def _fallback_text_parse(text: str) -> Dict:
        """Simple regex fallback for text parsing"""
        import re
        from datetime import timedelta
        
        # Extract amount
        amount_match = re.search(r'₹?\s*([\d,]+\.?\d*)\s*(k|kilo|thousand)?', text, re.I)
        amount = float(amount_match.group(1).replace(',', '')) if amount_match else 0
        if amount_match and amount_match.group(2):
            amount *= 1000
        
        # Extract counterparty (simple heuristic)
        cp_match = re.search(r'(?:to|from|pay|for)\s+([A-Z][a-zA-Z\s]+?)(?:\s+(?:of|₹|\d)|$)', text)
        counterparty = cp_match.group(1).strip() if cp_match else "Unknown"
        
        # Extract category
        text_lower = text.lower()
        category = "OTHER"
        if any(w in text_lower for w in ["gst", "tax"]): category = "GST"
        elif any(w in text_lower for w in ["rent", "lease"]): category = "RENT"
        elif any(w in text_lower for w in ["salary", "wage"]): category = "SALARY"
        elif any(w in text_lower for w in ["loan", "emi"]): category = "LOAN"
        
        # Direction
        direction = "IN" if any(w in text_lower for w in ["receive", "income", "paid to us"]) else "OUT"
        
        # Date (default: 7 days)
        due_date = (datetime.now() + timedelta(days=7)).date()
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', text)
        if date_match:
            due_date = datetime.strptime(date_match.group(1), "%Y-%m-%d").date()
        
        return {
            "counterparty_name": counterparty,
            "amount": amount,
            "due_date": due_date,
            "category": category,
            "direction": direction,
            "flexibility": "NONE" if category == "GST" else "DEFERRABLE",
            "relationship_score": 50,
            "consequence_score": 0.7 if category in ["GST", "SALARY"] else 0.4,
            "status": "PENDING"
        }

    @staticmethod
    def from_ocr(ocr_text: str) -> List[Dict]:
        """
        Parse OCR output → transactions
        Future: Integrate Tesseract/Google Vision
        For now: Treat as multi-line text input
        """
        lines = [l.strip() for l in ocr_text.split('\n') if l.strip()]
        transactions = []
        
        for line in lines:
            txn = InputLoader.from_text(line, use_llm=False)  # Use fallback for speed
            if txn:
                transactions.append(txn)
        
        print(f"📷 OCR: Extracted {len(transactions)} transactions from {len(lines)} lines")
        return transactions

    @staticmethod
    def load(
        source: str,
        source_type: str = "json"  # "json" | "text" | "ocr"
    ) -> Union[List[Dict], Dict, None]:
        """
        Unified entry point
        """
        if source_type == "json":
            return InputLoader.from_json(source)
        elif source_type == "text":
            return InputLoader.from_text(source)
        elif source_type == "ocr":
            return InputLoader.from_ocr(source)
        else:
            raise ValueError(f"Unknown source_type: {source_type}")