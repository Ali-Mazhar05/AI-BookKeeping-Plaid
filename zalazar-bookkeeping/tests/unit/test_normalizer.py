import pytest
from decimal import Decimal
from zalazar.normalizer import clean_vendor, infer_type

def test_clean_vendor_strips_processors():
    assert clean_vendor("SQ *THE COFFEE SHOP") == "The Coffee Shop"
    assert clean_vendor("APP APPLE.COM/BILL") == "Apple.Com/Bill" # wait, APP and APPLE.COM/BILL.
    # Actually, the rule replaces APPLE.COM/BILL. Let's test a simple one
    assert clean_vendor("SQ THE COFFEE SHOP") == "The Coffee Shop"

def test_clean_vendor_strips_marketplaces():
    assert clean_vendor("PAYPAL *UBER EATS") == "Uber Eats"
    assert clean_vendor("AMZN Mktp US") == "Us"

def test_clean_vendor_strips_tails():
    assert clean_vendor("HOME DEPOT *1234567") == "Home Depot"
    assert clean_vendor("TARGET 0987654321") == "Target"

def test_clean_vendor_strips_location():
    assert clean_vendor("THE HOME DEPOT #4455, GA") == "The Home Depot #4455"

def test_infer_type():
    assert infer_type(Decimal("50.00")) == "income"
    assert infer_type(Decimal("-25.50")) == "expense"
    assert infer_type(Decimal("0.00")) == "other"
