"""
Testing Tab - Individual Agent Testing and Health Checks
Modular design for easy expansion as new agents are added
"""

from datetime import datetime
import traceback

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, html
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

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
    },
    "agent_7": {
        "id": "7",
        "name": "Fact Verification Agent",
        "description": "Verify news claims and detect misinformation",
        "module": "src.agents.fact_verification_agent",
        "class": "FactVerificationAgent",
        "test_method": "test_fact_check",
        "expected_output": "fact check completed",
        "tier": "TIER 3: Analysis"
    },
    "agent_8": {
        "id": "8",
        "name": "Correlation Analysis Agent",
        "description": "Analyze correlations between news and market movements",
        "module": "src.agents.correlation_analysis_agent",
        "class": "CorrelationAnalysisAgent",
        "test_method": "test_correlation_calculation",
        "expected_output": "correlation calculated",
        "tier": "TIER 3: Analysis"
    },
    "agent_9": {
        "id": "9",
        "name": "Signal Decay Agent",
        "description": "Track news impact decay over time",
        "module": "src.agents.signal_decay_agent",
        "class": "SignalDecayAgent",
        "test_method": "test_decay_calculation",
        "expected_output": "decay calculated",
        "tier": "TIER 3: Analysis"
    },
    "agent_10": {
        "id": "10",
        "name": "Scenario Generation Agent",
        "description": "Generate market scenarios based on news",
        "module": "src.agents.scenario_generation_agent",
        "class": "ScenarioGenerationAgent",
        "test_method": "test_scenario_generation",
        "expected_output": "scenarios generated",
        "tier": "TIER 4: Prediction"
    },
    "agent_11": {
        "id": "11",
        "name": "Confidence Calibration Agent",
        "description": "Calibrate prediction confidence levels",
        "module": "src.agents.confidence_calibration_agent",
        "class": "ConfidenceCalibrationAgent",
        "test_method": "test_calibration",
        "expected_output": "confidence calibrated",
        "tier": "TIER 4: Prediction"
    },
    "agent_12": {
        "id": "12",
        "name": "Meta Strategy Agent",
        "description": "Optimize strategy selection and weighting",
        "module": "src.agents.meta_strategy_agent",
        "class": "MetaStrategyAgent",
        "test_method": "test_strategy_selection",
        "expected_output": "strategy selected",
        "tier": "TIER 5: Optimization"
    },
    "agent_13": {
        "id": "13",
        "name": "Model Performance Monitor",
        "description": "Monitor and analyze model performance",
        "module": "src.agents.model_performance_monitor",
        "class": "ModelPerformanceMonitor",
        "test_method": "test_performance_tracking",
        "expected_output": "performance tracked",
        "tier": "TIER 5: Optimization"
    },
    "agent_14": {
        "id": "14",
        "name": "A/B Testing Agent",
        "description": "Run A/B tests on strategies and models",
        "module": "src.agents.ab_testing_agent",
        "class": "ABTestingAgent",
        "test_method": "test_ab_testing",
        "expected_output": "A/B test executed",
        "tier": "TIER 5: Optimization"
    },
    "simulation_engine": {
        "id": "15",
        "name": "Trading Simulation Engine",
        "description": "Validate predicted market impact, risk scoring, and trade decisions",
        "module": "src.simulations.trading_simulator",
        "class": "TradingSimulationEngine",
        "test_method": "test_simulation_engine",
        "expected_output": "simulation checks passed",
        "tier": "TIER 6: Simulation"
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
    
    # List of refactored agents that DON'T need db parameter
    REFACTORED_AGENTS = {
        "agent_1_5",  # DataQualityAgent
        "agent_2",    # ContentUnderstandingAgent
        "agent_3",    # EntityMappingAgent
        "agent_4",    # ImpactScoringAgent
        "agent_4_5",  # SurpriseQuantificationAgent
        "agent_6",    # PredictionAgent
        "agent_7",    # FactVerificationAgent
        "agent_8",    # CorrelationAnalysisAgent
        "agent_9",    # SignalDecayAgent
        "agent_11",   # ConfidenceCalibrationAgent
        "agent_12",   # MetaStrategyAgent
        "simulation_engine",  # TradingSimulationEngine
    }
    
    try:
        # Dynamic import
        module_path = agent_info["module"]
        class_name = agent_info["class"]
        
        # Import module
        module = __import__(module_path, fromlist=[class_name])
        agent_class = getattr(module, class_name)
        
        # Initialize database session (for non-refactored agents)
        engine = create_engine(settings.database_url)
        db = Session(engine)
        
        # Initialize agent - REFACTORED agents don't need db parameter
        if agent_key in REFACTORED_AGENTS:
            agent = agent_class()  # ✅ No db parameter for refactored agents
        else:
            agent = agent_class(db)  # Old style for non-refactored agents
        
        # Check if agent has required methods
        required_methods = ['process_batch', '__init__']
        missing_methods = [m for m in required_methods if not hasattr(agent, m)]
        if missing_methods:
            db.close()
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
            # Test RSS feed connection - check class attribute
            rss_feeds = getattr(agent, 'RSS_FEEDS', None) or getattr(agent, 'rss_feeds', None)
            if rss_feeds and len(rss_feeds) > 0:
                return {"success": True, "message": f"Found {len(rss_feeds)} RSS feeds configured"}
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
            # Test entity extraction - check for process_batch (refactored)
            if hasattr(agent, 'process_batch'):
                return {"success": True, "message": "✅ Entity mapping agent ready (refactored)"}
            return {"success": False, "message": "Missing process_batch method"}
            
        elif agent_key == "agent_4":
            # Test impact calculation - check for process_batch (refactored)
            if hasattr(agent, 'process_batch'):
                return {"success": True, "message": "✅ Impact scoring agent ready (refactored)"}
            return {"success": False, "message": "Missing process_batch method"}
            
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
            # Test prediction generation - check for process_batch (refactored)
            if hasattr(agent, 'process_batch'):
                return {"success": True, "message": "✅ Prediction agent ready (refactored)"}
            return {"success": False, "message": "Missing process_batch method"}
        
        elif agent_key == "agent_7":
            # Test fact verification - check for process_batch (refactored)
            if hasattr(agent, 'process_batch'):
                return {"success": True, "message": "✅ Fact verification agent ready (refactored)"}
            return {"success": False, "message": "Missing process_batch method"}
        
        elif agent_key == "agent_8":
            # Test correlation analysis - check for process_batch (refactored)
            if hasattr(agent, 'process_batch'):
                return {"success": True, "message": "✅ Correlation agent ready (refactored)"}
            return {"success": False, "message": "Missing process_batch method"}
        
        elif agent_key == "agent_9":
            # Test signal decay - check for process_batch (refactored)
            if hasattr(agent, 'process_batch'):
                return {"success": True, "message": "✅ Signal decay agent ready (refactored)"}
            return {"success": False, "message": "Missing process_batch method"}

        elif agent_key == "simulation_engine":
            # Test risk calculation and trading simulation utilities (no DB/network calls)
            from src.simulations.risk_calculations import RiskCalculator, RiskInputs

            calculator = RiskCalculator()
            inputs = RiskInputs(
                model_uncertainty=0.2,
                divergence_pct=2.5,
                volatility_regime="medium",
                liquidity_stress=0.3,
                regime_confidence=0.7,
                transaction_cost_ratio=0.2,
                market_impact_bps=6.0,
                correlation_breakdown=0.1,
            )
            risk_result = calculator.calculate(inputs)
            risk_score = risk_result.get("risk_score")
            if risk_score is None or not (0.0 <= risk_score <= 1.0):
                return {
                    "success": False,
                    "message": "Risk score out of bounds",
                    "risk_result": risk_result,
                }

            # Validate predicted return normalization behavior
            class _PredictionStub:
                expected_return = {"mean": 0.02}

            expected_return_pct = agent._get_expected_return_pct(_PredictionStub())
            if abs(expected_return_pct - 2.0) > 0.001:
                return {
                    "success": False,
                    "message": "Expected return normalization failed",
                    "expected_return_pct": expected_return_pct,
                }

            # Validate cost estimation and decision logic
            total_bps, breakdown = agent._estimate_costs_bps(price=150.0, volatility_regime="medium")
            if total_bps <= 0 or not breakdown:
                return {
                    "success": False,
                    "message": "Cost estimation failed",
                    "cost_breakdown": breakdown,
                }

            decision = agent._calculate_decision(
                predicted_direction="up",
                expected_return_pct=2.0,
                confidence=0.8,
                risk_score=0.4,
                cost_ratio=0.2,
            )
            if decision != "buy":
                return {
                    "success": False,
                    "message": f"Unexpected decision outcome: {decision}",
                    "decision": decision,
                }

            # Validate market snapshot handling with stubbed provider
            class _StaticMarketDataProvider:
                def get_live_price(self, ticker):
                    return {
                        "symbol": ticker,
                        "price": 123.45,
                        "change_percent": 0.12,
                        "timestamp": datetime.utcnow(),
                    }

            agent.market_data_provider = _StaticMarketDataProvider()
            snapshot = agent._get_market_snapshot("TEST")
            if not snapshot or snapshot.get("price") is None:
                return {
                    "success": False,
                    "message": "Market snapshot missing price",
                    "snapshot": snapshot,
                }

            return {
                "success": True,
                "message": "Risk, market data, and decision checks passed",
                "risk_score": risk_score,
                "decision": decision,
            }
            
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


def register_callbacks(app):
    """Register testing tab callbacks."""

    for agent_key in AGENT_TESTS.keys():
        @app.callback(
            [
                Output(f"result-{agent_key}", "children"),
                Output(f"badge-{agent_key}", "children"),
                Output(f"badge-{agent_key}", "color"),
                Output(f"btn-details-{agent_key}", "disabled"),
                Output("store-test-results", "data", allow_duplicate=True),
            ],
            Input(f"btn-test-{agent_key}", "n_clicks"),
            State("store-test-results", "data"),
            prevent_initial_call=True,
        )
        def _test_single_agent(n_clicks, test_results, _key=agent_key):
            if not n_clicks:
                return dash.no_update
            success, message, details = test_agent(_key)
            test_results = test_results or {}
            test_results[_key] = {
                "success": success,
                "message": message,
                "details": details,
                "timestamp": datetime.now().isoformat(),
            }
            result_display = format_test_result(success, message, details)
            badge_text = "✅ Pass" if success else "❌ Fail"
            badge_color = "success" if success else "danger"
            details_disabled = not bool(details.get("traceback"))
            return result_display, badge_text, badge_color, details_disabled, test_results

    @app.callback(
        [
            Output("store-test-results", "data", allow_duplicate=True),
            Output("test-summary", "children"),
        ],
        Input("btn-test-all", "n_clicks"),
        prevent_initial_call=True,
    )
    def _test_all_agents(n_clicks):
        if not n_clicks:
            return dash.no_update
        test_results = {}
        for k in AGENT_TESTS.keys():
            success, message, details = test_agent(k)
            test_results[k] = {
                "success": success,
                "message": message,
                "details": details,
                "timestamp": datetime.now().isoformat(),
            }
        return test_results, get_test_summary(test_results)

    @app.callback(
        Output("test-summary", "children", allow_duplicate=True),
        Input("store-test-results", "data"),
        prevent_initial_call=True,
    )
    def _update_test_summary(test_results):
        return get_test_summary(test_results)

    @app.callback(
        Output("store-test-results", "data", allow_duplicate=True),
        Input("btn-reset-tests", "n_clicks"),
        prevent_initial_call=True,
    )
    def _reset_tests(n_clicks):
        if not n_clicks:
            return dash.no_update
        return {}

    for agent_key in AGENT_TESTS.keys():
        @app.callback(
            [
                Output(f"badge-{agent_key}", "children", allow_duplicate=True),
                Output(f"badge-{agent_key}", "color", allow_duplicate=True),
                Output(f"result-{agent_key}", "children", allow_duplicate=True),
                Output(f"btn-details-{agent_key}", "disabled", allow_duplicate=True),
            ],
            Input("store-test-results", "data"),
            prevent_initial_call=True,
        )
        def _update_agent_status_from_store(test_results, _key=agent_key):
            if not test_results or _key not in test_results:
                return "", "secondary", "", True
            r = test_results[_key]
            success = r.get("success", False)
            message = r.get("message", "")
            details = r.get("details", {})
            badge_text = "✅ Pass" if success else "❌ Fail"
            badge_color = "success" if success else "danger"
            result_display = format_test_result(success, message, details)
            details_disabled = not bool(details.get("traceback"))
            return badge_text, badge_color, result_display, details_disabled

    for agent_key in AGENT_TESTS.keys():
        @app.callback(
            [
                Output("error-modal", "is_open", allow_duplicate=True),
                Output("error-detail-content", "children", allow_duplicate=True),
            ],
            Input(f"btn-details-{agent_key}", "n_clicks"),
            State("store-test-results", "data"),
            prevent_initial_call=True,
        )
        def _show_error_details(n_clicks, test_results, _key=agent_key):
            if not n_clicks or not test_results or _key not in test_results:
                return False, ""
            r = test_results[_key]
            details = r.get("details", {})
            meta = AGENT_TESTS[_key]
            parts = [
                html.H5(f"Agent {meta['id']}: {meta['name']}"),
                html.Hr(),
                html.H6("Error Message:"),
                html.Pre(r.get("message", "No message"), className="bg-dark p-3 text-light"),
                html.H6("Details:", className="mt-3"),
                html.Pre(details.get("error", "No details"), className="bg-dark p-3 text-light"),
            ]
            if details.get("traceback"):
                parts.append(html.H6("Traceback:", className="mt-3"))
                parts.append(html.Pre(details.get("traceback", ""), className="bg-dark p-3 text-light", style={"fontSize": "11px"}))
            content = html.Div(parts)
            return True, content

    @app.callback(
        Output("error-modal", "is_open", allow_duplicate=True),
        Input("close-error-modal", "n_clicks"),
        prevent_initial_call=True,
    )
    def _close_error_modal(n_clicks):
        return False
