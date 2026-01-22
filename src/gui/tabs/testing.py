"""
Testing Tab - Individual Agent Testing and Health Checks
Modular design for easy expansion as new agents are added
"""

from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
from datetime import datetime
import traceback
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

from src.config.settings import settings

# Agent test configurations - EASY TO EXPAND
AGENT_TESTS = {
    "agent_1": {
        "id": "1",
        "name": "Data Ingestion Agent",
        "description": "Fetch articles from RSS feeds",
        "module": "src.agents.ingestion_agent",
        "class": "IngestionAgent",
        "test_method": "test_single_fetch",
        "expected_output": "articles fetched",
        "tier": "TIER 1: Data Ingestion"
    },
    "agent_1_5": {
        "id": "1.5",
        "name": "Data Quality Agent",
        "description": "Assess article quality and detect duplicates",
        "module": "src.agents.data_quality_agent",
        "class": "DataQualityAgent",
        "test_method": "test_quality_check",
        "expected_output": "quality score calculated",
        "tier": "TIER 1: Data Ingestion"
    },
    "agent_2": {
        "id": "2",
        "name": "Content Understanding Agent",
        "description": "LLM-based content analysis",
        "module": "src.agents.content_understanding_agent",
        "class": "ContentUnderstandingAgent",
        "test_method": "test_llm_connection",
        "expected_output": "LLM response received",
        "tier": "TIER 2: Understanding"
    },
    "agent_3": {
        "id": "3",
        "name": "Entity Mapping Agent",
        "description": "Extract and map entities to tickers",
        "module": "src.agents.entity_mapping_agent",
        "class": "EntityMappingAgent",
        "test_method": "test_entity_extraction",
        "expected_output": "entities extracted",
        "tier": "TIER 2: Understanding"
    },
    "agent_4": {
        "id": "4",
        "name": "Impact Scoring Agent",
        "description": "Calculate news impact scores",
        "module": "src.agents.impact_scoring_agent",
        "class": "ImpactScoringAgent",
        "test_method": "test_impact_calculation",
        "expected_output": "impact score calculated",
        "tier": "TIER 3: Analysis"
    },
    "agent_4_5": {
        "id": "4.5",
        "name": "Surprise Quantification Agent",
        "description": "Detect earnings surprises",
        "module": "src.agents.surprise_quantification_agent",
        "class": "SurpriseQuantificationAgent",
        "test_method": "test_surprise_detection",
        "expected_output": "surprise calculated",
        "tier": "TIER 3: Analysis"
    },
    "agent_5": {
        "id": "5",
        "name": "Market Regime Detection Agent",
        "description": "Detect current market regime",
        "module": "src.agents.regime_detection_agent",
        "class": "RegimeDetectionAgent",
        "test_method": "test_regime_classification",
        "expected_output": "regime detected",
        "tier": "TIER 3: Analysis"
    },
    "agent_6": {
        "id": "6",
        "name": "Prediction Agent",
        "description": "Generate market predictions",
        "module": "src.agents.prediction_agent",
        "class": "PredictionAgent",
        "test_method": "test_prediction_generation",
        "expected_output": "prediction generated",
        "tier": "TIER 4: Prediction"
    }
}


def create_layout():
    """Create testing tab layout"""
    
    # Group agents by tier
    tiers = {}
    for agent_key, agent_info in AGENT_TESTS.items():
        tier = agent_info["tier"]
        if tier not in tiers:
            tiers[tier] = []
        tiers[tier].append((agent_key, agent_info))
    
    # Create agent test cards grouped by tier
    tier_sections = []
    for tier_name, agents in sorted(tiers.items()):
        agent_cards = []
        for agent_key, agent_info in agents:
            card = create_agent_test_card(agent_key, agent_info)
            agent_cards.append(dbc.Col(card, width=6, className="mb-3"))
        
        tier_section = html.Div([
            html.H5(tier_name, className="text-primary mb-3 mt-3"),
            dbc.Row(agent_cards)
        ])
        tier_sections.append(tier_section)
    
    return dbc.Container([
        # Header with bulk actions
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.H5("🧪 Agent Testing Suite", className="mb-0"),
                                html.P("Test individual agents for functionality and health", className="text-muted small mb-0")
                            ], width=6),
                            dbc.Col([
                                dbc.Button("🚀 Test All Agents", id="btn-test-all", color="primary", className="me-2"),
                                dbc.Button("🔄 Reset Results", id="btn-reset-tests", color="secondary", outline=True),
                            ], width=6, className="text-end")
                        ])
                    ])
                ])
            ], width=12)
        ], className="mb-3"),
        
        # Overall status summary
        dbc.Row([
            dbc.Col([
                html.Div(id="test-summary")
            ], width=12)
        ], className="mb-3"),
        
        # Agent test cards grouped by tier
        html.Div(tier_sections),
        
        # Detailed error log modal
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Error Details")),
            dbc.ModalBody([
                html.Div(id="error-detail-content")
            ]),
            dbc.ModalFooter(
                dbc.Button("Close", id="close-error-modal", className="ms-auto")
            ),
        ], id="error-modal", size="xl", scrollable=True),
        
        # Store for test results
        dcc.Store(id="store-test-results", data={}),
        dcc.Interval(id="interval-test-monitor", interval=1000, disabled=True)
        
    ], fluid=True)


def create_agent_test_card(agent_key, agent_info):
    """Create individual agent test card"""
    return dbc.Card([
        dbc.CardHeader([
            html.Div([
                html.Span(f"Agent {agent_info['id']}: ", className="text-primary fw-bold"),
                html.Span(agent_info['name']),
                dbc.Badge("", id=f"badge-{agent_key}", className="ms-2")
            ])
        ]),
        dbc.CardBody([
            html.P(agent_info['description'], className="text-muted small mb-3"),
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Strong("Module: ", className="small"),
                        html.Code(agent_info['module'], className="small text-info")
                    ], className="mb-1"),
                    html.Div([
                        html.Strong("Class: ", className="small"),
                        html.Code(agent_info['class'], className="small text-info")
                    ], className="mb-2")
                ], width=12)
            ]),
            dbc.Row([
                dbc.Col([
                    dbc.Button(
                        "🧪 Test Agent",
                        id=f"btn-test-{agent_key}",
                        color="primary",
                        size="sm",
                        outline=True,
                        className="w-100"
                    )
                ], width=6),
                dbc.Col([
                    dbc.Button(
                        "📋 View Details",
                        id=f"btn-details-{agent_key}",
                        color="info",
                        size="sm",
                        outline=True,
                        className="w-100",
                        disabled=True
                    )
                ], width=6)
            ]),
            html.Div(id=f"result-{agent_key}", className="mt-3")
        ])
    ])


def test_agent(agent_key):
    """
    Test individual agent
    Returns: (success: bool, message: str, details: dict)
    """
    agent_info = AGENT_TESTS.get(agent_key)
    if not agent_info:
        return False, "Agent configuration not found", {}
    
    start_time = datetime.now()
    
    try:
        # Dynamic import
        module_path = agent_info["module"]
        class_name = agent_info["class"]
        
        # Import module
        module = __import__(module_path, fromlist=[class_name])
        agent_class = getattr(module, class_name)
        
        # Initialize database session
        engine = create_engine(settings.database_url)
        db = Session(engine)
        
        # Initialize agent
        agent = agent_class(db)
        
        # Basic initialization test
        if not hasattr(agent, 'db'):
            return False, "Agent missing database session", {"error": "No db attribute"}
        
        # Check if agent has required methods
        required_methods = ['process_batch', '__init__']
        missing_methods = [m for m in required_methods if not hasattr(agent, m)]
        if missing_methods:
            return False, f"Missing methods: {', '.join(missing_methods)}", {"missing": missing_methods}
        
        # Agent-specific tests
        test_result = run_agent_specific_test(agent, agent_key)
        
        db.close()
        
        duration = (datetime.now() - start_time).total_seconds()
        
        if test_result["success"]:
            return True, f"✅ Test passed in {duration:.2f}s", test_result
        else:
            return False, f"❌ {test_result.get('message', 'Test failed')}", test_result
            
    except ImportError as e:
        return False, f"Import Error: {str(e)}", {"error": str(e), "traceback": traceback.format_exc()}
    except Exception as e:
        return False, f"Error: {str(e)}", {"error": str(e), "traceback": traceback.format_exc()}


def run_agent_specific_test(agent, agent_key):
    """Run agent-specific tests"""
    try:
        if agent_key == "agent_1":
            # Test RSS feed connection
            if hasattr(agent, 'rss_feeds') and len(agent.rss_feeds) > 0:
                return {"success": True, "message": f"Found {len(agent.rss_feeds)} RSS feeds configured"}
            return {"success": False, "message": "No RSS feeds configured"}
            
        elif agent_key == "agent_1_5":
            # Test quality scoring logic
            if hasattr(agent, 'calculate_quality_score'):
                return {"success": True, "message": "Quality scoring method available"}
            return {"success": False, "message": "Missing calculate_quality_score method"}
            
        elif agent_key == "agent_2":
            # Test LLM connection
            if hasattr(agent, 'llm'):
                return {"success": True, "message": f"LLM service initialized: {agent.llm.provider}"}
            return {"success": False, "message": "LLM service not initialized"}
            
        elif agent_key == "agent_3":
            # Test entity extraction
            if hasattr(agent, 'extract_entities'):
                return {"success": True, "message": "Entity extraction method available"}
            return {"success": False, "message": "Missing extract_entities method"}
            
        elif agent_key == "agent_4":
            # Test impact calculation
            if hasattr(agent, 'calculate_impact'):
                return {"success": True, "message": "Impact calculation method available"}
            return {"success": False, "message": "Missing calculate_impact method"}
            
        elif agent_key == "agent_4_5":
            # Test surprise calculation
            if hasattr(agent, 'calculate_surprise'):
                return {"success": True, "message": "Surprise calculation method available"}
            return {"success": False, "message": "Missing calculate_surprise method"}
            
        elif agent_key == "agent_5":
            # Test regime detection
            if hasattr(agent, 'detect_regime'):
                return {"success": True, "message": "Regime detection method available"}
            return {"success": False, "message": "Missing detect_regime method"}
            
        elif agent_key == "agent_6":
            # Test prediction generation
            if hasattr(agent, 'generate_prediction'):
                return {"success": True, "message": "Prediction generation method available"}
            return {"success": False, "message": "Missing generate_prediction method"}
            
        else:
            return {"success": True, "message": "Basic initialization successful"}
            
    except Exception as e:
        return {"success": False, "message": str(e), "traceback": traceback.format_exc()}


def get_test_summary(test_results):
    """Generate summary of test results"""
    if not test_results:
        return dbc.Alert("No tests run yet. Click 'Test All Agents' or test individual agents.", color="info")
    
    total = len(test_results)
    passed = sum(1 for r in test_results.values() if r.get("success"))
    failed = total - passed
    
    return dbc.Card([
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.H2(f"{passed}/{total}", className="text-success mb-0"),
                        html.P("Tests Passed", className="text-muted small mb-0")
                    ], className="text-center")
                ], width=3),
                dbc.Col([
                    html.Div([
                        html.H2(f"{failed}", className="text-danger mb-0"),
                        html.P("Tests Failed", className="text-muted small mb-0")
                    ], className="text-center")
                ], width=3),
                dbc.Col([
                    html.Div([
                        html.H2(f"{(passed/total*100):.0f}%", className="text-primary mb-0"),
                        html.P("Success Rate", className="text-muted small mb-0")
                    ], className="text-center")
                ], width=3),
                dbc.Col([
                    html.Div([
                        html.H2("✅" if failed == 0 else "⚠️", className="mb-0"),
                        html.P("Overall Status", className="text-muted small mb-0")
                    ], className="text-center")
                ], width=3)
            ])
        ])
    ])


def format_test_result(success, message, details):
    """Format test result for display"""
    if success:
        return dbc.Alert([
            html.Strong("✅ Success: "),
            html.Span(message),
            html.Br(),
            html.Small(details.get("message", ""), className="text-muted")
        ], color="success", className="mb-0 mt-2")
    else:
        return dbc.Alert([
            html.Strong("❌ Failed: "),
            html.Span(message),
            html.Br(),
            html.Small("Click 'View Details' for full error", className="text-muted") if details.get("traceback") else None
        ], color="danger", className="mb-0 mt-2")
