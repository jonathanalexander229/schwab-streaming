# debug_flask_routes.py - Debug the Flask web server issues

import os
from flask import Flask

def check_flask_app_issues():
    """Check common Flask app issues that prevent pages from loading"""
    print("="*60)
    print("DEBUGGING FLASK WEB SERVER ISSUES")
    print("="*60)
    
    # 1. Check if routes are properly registered
    print("1. CHECKING ROUTE REGISTRATION")
    print("-" * 30)
    
    try:
        # Import your actual app
        from app import app
        
        # List all registered routes
        print("Registered routes:")
        for rule in app.url_map.iter_rules():
            print(f"  {rule.endpoint}: {rule.rule} [{', '.join(rule.methods)}]")
        
        # Check specific routes
        critical_routes = ['index', 'login', 'authenticate']
        for route in critical_routes:
            if route in [rule.endpoint for rule in app.url_map.iter_rules()]:
                print(f"✅ {route} route registered")
            else:
                print(f"❌ {route} route MISSING")
        
    except Exception as e:
        print(f"❌ Error importing app: {e}")
        return False
    
    # 2. Check template and static file paths
    print(f"\n2. CHECKING FILE PATHS")
    print("-" * 30)
    
    try:
        print(f"Template folder: {app.template_folder}")
        print(f"Static folder: {app.static_folder}")
        
        # Check if directories exist
        if os.path.exists(app.template_folder):
            templates = os.listdir(app.template_folder)
            print(f"✅ Templates exist: {templates}")
        else:
            print(f"❌ Template folder missing: {app.template_folder}")
        
        if os.path.exists(app.static_folder):
            print(f"✅ Static folder exists")
        else:
            print(f"❌ Static folder missing: {app.static_folder}")
    
    except Exception as e:
        print(f"❌ Error checking paths: {e}")
    
    # 3. Test route responses
    print(f"\n3. TESTING ROUTE RESPONSES")
    print("-" * 30)
    
    try:
        with app.test_client() as client:
            # Test root route
            response = client.get('/')
            print(f"GET /: {response.status_code}")
            if response.status_code == 302:
                print(f"  Redirects to: {response.location}")
            elif response.status_code != 200:
                print(f"  Response data: {response.data[:100]}")
            
            # Test login route
            response = client.get('/login')
            print(f"GET /login: {response.status_code}")
            if response.status_code != 200:
                print(f"  Response data: {response.data[:100]}")
            
    except Exception as e:
        print(f"❌ Error testing routes: {e}")
        import traceback
        traceback.print_exc()
    
    # 4. Check session/authentication flow
    print(f"\n4. CHECKING SESSION/AUTH FLOW")
    print("-" * 30)
    
    try:
        from app import session, global_mock_mode
        
        print(f"Global mock mode: {global_mock_mode}")
        
        # Test auth flow
        with app.test_client() as client:
            with client.session_transaction() as sess:
                print(f"Empty session keys: {list(sess.keys())}")
            
            # Simulate authentication
            response = client.get('/authenticate')
            print(f"GET /authenticate: {response.status_code}")
            if response.status_code == 302:
                print(f"  Redirects to: {response.location}")
    
    except Exception as e:
        print(f"❌ Error checking auth flow: {e}")
        import traceback
        traceback.print_exc()
    
    return True

def check_missing_functions():
    """Check if any required functions are missing"""
    print(f"\n5. CHECKING FOR MISSING FUNCTIONS")
    print("-" * 30)
    
    try:
        from app import app
        
        # Check if the functions called in initialize_app exist
        required_functions = ['create_static_files', 'create_templates']
        
        for func_name in required_functions:
            if hasattr(app, func_name) or func_name in globals():
                print(f"✅ {func_name} exists")
            else:
                print(f"❌ {func_name} MISSING - this could cause initialization to fail")
        
    except Exception as e:
        print(f"❌ Error checking functions: {e}")

def test_minimal_flask():
    """Test if Flask works with minimal setup"""
    print(f"\n6. TESTING MINIMAL FLASK APP")
    print("-" * 30)
    
    try:
        test_app = Flask(__name__)
        test_app.config['SECRET_KEY'] = 'test'
        
        @test_app.route('/')
        def test_index():
            return "Test Flask app works!"
        
        with test_app.test_client() as client:
            response = client.get('/')
            print(f"Minimal Flask test: {response.status_code}")
            print(f"Response: {response.data.decode()}")
        
        print("✅ Basic Flask functionality works")
        
    except Exception as e:
        print(f"❌ Basic Flask test failed: {e}")

def main():
    """Run all debugging checks"""
    print("This will debug Flask web server issues in your app")
    print("Make sure you're in the directory with app.py")
    print()
    
    check_flask_app_issues()
    check_missing_functions() 
    test_minimal_flask()
    
    print(f"\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print("Look for any ❌ errors above.")
    print("Common issues:")
    print("- Missing routes")
    print("- Missing template files") 
    print("- Missing static files")
    print("- Authentication flow problems")
    print("- Missing required functions")

if __name__ == "__main__":
    main()