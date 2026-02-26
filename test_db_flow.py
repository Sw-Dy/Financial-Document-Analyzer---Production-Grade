#!/usr/bin/env python
"""
Test script to verify database session lifecycle and task retrieval.

Tests:
1. Create analysis record via CRUD
2. Query it back immediately 
3. Verify Celery task can update it
"""

import uuid
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize database
from db import SessionLocal, init_db
from models import AnalysisResult, User
from crud import create_analysis, get_analysis, update_analysis_result

def test_database_flow():
    """Test the complete database flow."""
    
    print("\n" + "="*60)
    print("DATABASE SESSION LIFECYCLE TEST")
    print("="*60)
    
    # Initialize database
    print("\n[Setup] Initializing database...")
    init_db()
    
    # Generate unique task_id
    task_id = str(uuid.uuid4())
    print(f"\n[Test] Generated task_id: {task_id}")
    
    # TEST 1: Create analysis record
    print("\n[Test 1] Creating analysis record...")
    session1 = SessionLocal()
    try:
        analysis1 = create_analysis(
            session=session1,
            task_id=task_id,
            filename="test_document.pdf",
            user_id=None,
        )
        print(f"✓ Record created: status={analysis1.status}, id={analysis1.id}")
    finally:
        session1.close()
        print("✓ Session 1 closed")
    
    # TEST 2: Query it back with NEW session
    print("\n[Test 2] Querying record with fresh session...")
    session2 = SessionLocal()
    try:
        analysis2 = get_analysis(session2, task_id)
        if analysis2:
            print(f"✓ Record found: status={analysis2.status}, id={analysis2.id}")
        else:
            print(f"✗ ERROR: Record NOT found!")
            return False
    finally:
        session2.close()
        print("✓ Session 2 closed")
    
    # TEST 3: Update record with Celery-style session
    print("\n[Test 3] Updating record (simulating Celery task)...")
    session3 = SessionLocal()
    try:
        result_json = {
            "revenue": "$1M",
            "profit": "$0.5M",
            "recommendation": "BUY",
            "confidence": 85,
        }
        analysis3 = update_analysis_result(
            session=session3,
            task_id=task_id,
            status="completed",
            result_json=result_json,
        )
        if analysis3:
            print(f"✓ Record updated: status={analysis3.status}")
            print(f"  completed_at={analysis3.completed_at}")
        else:
            print(f"✗ ERROR: Could not update record!")
            return False
    finally:
        session3.close()
        print("✓ Session 3 closed")
    
    # TEST 4: Query updated record
    print("\n[Test 4] Querying updated record...")
    session4 = SessionLocal()
    try:
        analysis4 = get_analysis(session4, task_id)
        if analysis4:
            print(f"✓ Record found: status={analysis4.status}")
            print(f"  result_json={analysis4.result_json}")
            print(f"  completed_at={analysis4.completed_at}")
            if analysis4.status == "completed" and analysis4.result_json:
                print("\n✓ SUCCESS: Database flow working correctly!")
                return True
            else:
                print("\n✗ ERROR: Record not properly updated!")
                return False
        else:
            print(f"✗ ERROR: Record NOT found!")
            return False
    finally:
        session4.close()
        print("✓ Session 4 closed")


if __name__ == "__main__":
    try:
        success = test_database_flow()
        print("\n" + "="*60)
        if success:
            print("DATABASE TESTS PASSED ✓")
        else:
            print("DATABASE TESTS FAILED ✗")
        print("="*60 + "\n")
    except Exception as e:
        print(f"\n✗ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
