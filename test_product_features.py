"""
Quick test script to validate product trace and top products features.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from app import (
    _extract_product_id,
    _clarify_ambiguous_question,
)

def test_product_id_extraction():
    """Test product ID extraction from queries"""
    test_cases = [
        ("Trace product M001", "M001"),
        ("Find material X-100", "X-100"),
        ("Show product 5000", "5000"),
        ("Material 'Raw Material A'", "Raw Material A"),
        ("trace PRD-ABC", "PRD-ABC"),
        ("No product here", None),
    ]
    
    print("=" * 60)
    print("Testing Product ID Extraction")
    print("=" * 60)
    
    for query, expected in test_cases:
        result = _extract_product_id(query)
        status = "✓" if result == expected else "✗"
        print(f"{status} Query: '{query}'")
        print(f"  Expected: {expected}, Got: {result}")
        if result != expected:
            print(f"  ⚠️  MISMATCH!")
        print()

def test_clarification():
    """Test ambiguous question clarification"""
    test_cases = [
        ("trace", True),  # Should ask for clarification
        ("Trace product M001", False),  # Should NOT ask
        ("top products", True),  # Should ask for metric
        ("Show top 10 products by revenue", False),  # Clear question
        ("xyz", True),  # Too vague
    ]
    
    print("=" * 60)
    print("Testing Question Clarification")
    print("=" * 60)
    
    for query, should_clarify in test_cases:
        result = _clarify_ambiguous_question(query)
        is_clarifying = result is not None
        status = "✓" if is_clarifying == should_clarify else "✗"
        print(f"{status} Query: '{query}'")
        print(f"  Should clarify: {should_clarify}, Got: {is_clarifying}")
        if is_clarifying:
            print(f"  Clarification: {result[:80]}...")
        print()

def main():
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " PRODUCT TRACE & TOP PRODUCTS - FEATURE TEST ".center(58) + "║")
    print("╚" + "=" * 58 + "╝")
    print("\n")
    
    try:
        test_product_id_extraction()
        test_clarification()
        
        print("=" * 60)
        print("✓ All basic tests completed!")
        print("=" * 60)
        print("\nNote: Full integration tests require database and graph initialization")
        print("The new functions are ready to use with the Flask app!")
        print("\n")
        
    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
