# Test Files Summary

This document provides a summary of the Python test files found in the `tests` directory, outlining their purpose, relative path, and key functions or classes tested.

---

## `tests/test_update_logic.py`
*   **Purpose:** Test the logic for updating prediction performance records in the database. It verifies that recalculating and saving performance data correctly updates existing entries, specifically checking for timestamp changes.
*   **Key Functions/Classes Tested:**
    *   `src.models.predictions.Prediction`
    *   `src.models.predictions.PredictionOutcome`
    *   `src.models.entities.Entity`
    *   `src.services.prediction_performance_service.prediction_performance_service.get_prediction_performance`
    *   `src.services.prediction_performance_service.prediction_performance_service.save_prediction_performance`

---

## `tests/test_statistics_filter.py`
*   **Purpose:** This script tests the time period filtering functionality within the Statistics tab of the GUI. It verifies that statistics metrics can be retrieved without filters and with different date range filters (30-day, 7-day). It also checks for the presence of filter controls in the generated layout.
*   **Key Functions/Classes Tested:**
    *   `src.gui.tabs.statistics.get_statistics_metrics`
    *   `src.gui.tabs.statistics.create_layout`
    *   `src.models.database.engine`
    *   `test_statistics_filter`

---

## `tests/test_simulation.py`
*   **Purpose:** This script tests the `TradingSimulationAgent` by creating an agent instance, retrieving its current statistics, processing a batch of predictions, and then retrieving updated statistics to verify the agent's functionality.
*   **Key Functions/Classes Tested:**
    *   `src.agents.trading_simulation_agent.TradingSimulationAgent`
    *   `TradingSimulationAgent.get_statistics`
    *   `TradingSimulationAgent.process_batch`

---

## `tests/test_simple.py`
*   **Purpose:** This script performs a simple sanity check of the project's basic setup. It verifies that core components like database models, configuration settings, and a key agent (`IngestionAgent`) can be imported and initialized successfully. It also tests a basic database connection and query.
*   **Key Functions/Classes Tested:**
    *   `src.models.database.SessionLocal`
    *   `src.models.database.engine`
    *   `src.config.settings.settings`
    *   `src.agents.ingestion_agent.IngestionAgent`
    *   `src.models.raw_news.RawNews`
    *   `IngestionAgent.get_statistics`

---

## `tests/test_refactored_pipeline.py`
*   **Purpose:** This script serves as a quick test for the refactored pipeline agents. It primarily verifies that various agents can be instantiated without a database parameter, which is a key aspect of the refactoring. It also checks if certain agents have and can call a `get_statistics()` method.
*   **Key Functions/Classes Tested:**
    *   `src.agents.data_quality_agent.DataQualityAgent`
    *   `src.agents.content_understanding_agent.ContentUnderstandingAgent`
    *   `src.agents.entity_mapping_agent.EntityMappingAgent`
    *   `src.agents.impact_scoring_agent.ImpactScoringAgent`
    *   `src.agents.prediction_agent.PredictionAgent`
    *   `src.agents.surprise_quantification_agent.SurpriseQuantificationAgent`
    *   `src.agents.fact_verification_agent.FactVerificationAgent`
    *   `src.agents.signal_decay_agent.SignalDecayAgent`
    *   `src.agents.correlation_analysis_agent.CorrelationAnalysisAgent`
    *   `Agent.get_statistics`
    *   `test_agent_initialization`
    *   `test_agent_statistics`

---

## `tests/test_quick.py`
*   **Purpose:** This script performs a quick 'Minimum Viable Product (MVP)' test of several pipeline agents by processing only one article through each of them. It aims to verify that the core agents in the pipeline can be instantiated and execute their `process_batch` method (or `update_regime` for `RegimeDetectionAgent`) without errors.
*   **Key Functions/Classes Tested:**
    *   `src.models.database.SessionLocal`
    *   `src.agents.ingestion_agent.IngestionAgent`
    *   `src.agents.data_quality_agent.DataQualityAgent`
    *   `src.agents.content_understanding_agent.ContentUnderstandingAgent`
    *   `src.agents.entity_mapping_agent.EntityMappingAgent`
    *   `src.agents.surprise_quantification_agent.SurpriseQuantificationAgent`
    *   `src.agents.regime_detection_agent.RegimeDetectionAgent`
    *   `src.agents.impact_scoring_agent.ImpactScoringAgent`
    *   `src.agents.prediction_agent.PredictionAgent`

---

## `tests/test_predictions_simulations_integration.py`
*   **Purpose:** This script tests the integration between the Predictions and Simulations tabs in the GUI. It verifies that required modules can be imported, that prediction details can load associated simulation data, and that the simulation table correctly includes a 'details' button.
*   **Key Functions/Classes Tested:**
    *   `src.gui.tabs.predictions`
    *   `src.gui.tabs.simulations`
    *   `src.models.trading_simulation.TradingSimulation`
    *   `src.models.predictions.Prediction`
    *   `src.gui.tabs.predictions.get_prediction_details`
    *   `src.models.database.get_scoped_session`
    *   `src.models.database.engine`
    *   `src.gui.tabs.simulations.get_simulation_table`
    *   `test_imports`
    *   `test_prediction_details_with_simulation`
    *   `test_simulation_table_with_details_button`

---

## `tests/test_new_simulation_features.py`
*   **Purpose:** This script tests new features related to trading simulations, specifically the ability to create simulations from predictions with filters, refresh an existing simulation, and delete a simulation.
*   **Key Functions/Classes Tested:**
    *   `src.simulations.trading_simulator.TradingSimulationEngine`
    *   `TradingSimulationEngine.create_simulations_from_predictions`
    *   `TradingSimulationEngine.refresh_simulation`
    *   `TradingSimulationEngine.delete_simulation`
    *   `src.models.database.get_scoped_session`
    *   `src.models.trading_simulation.TradingSimulation`
    *   `test_create_simulations`
    *   `test_refresh_simulation`
    *   `test_delete_simulation`

---

## `tests/test_new_agents.py`
*   **Purpose:** This script provides comprehensive tests for several newly implemented agents, specifically Fact Verification Agent, Signal Decay Agent, Correlation Analysis Agent, Confidence Calibration Agent, Meta-Strategy Agent, Scenario Generation Agent, Model Performance Monitor, and A/B Testing Agent. It tests their initialization, statistics retrieval, and core functionalities.
*   **Key Functions/Classes Tested:**
    *   `src.models.database.get_db`
    *   `src.agents.fact_verification_agent.FactVerificationAgent`
    *   `src.agents.signal_decay_agent.SignalDecayAgent`
    *   `src.agents.correlation_analysis_agent.CorrelationAnalysisAgent`
    *   `src.agents.confidence_calibration_agent.ConfidenceCalibrationAgent`
    *   `src.agents.meta_strategy_agent.MetaStrategyAgent`
    *   `src.agents.scenario_generation_agent.ScenarioGenerationAgent`
    *   `src.agents.model_performance_monitor.ModelPerformanceMonitor`
    *   `src.agents.ab_testing_agent.ABTestingAgent`
    *   Individual `test_` functions for each agent

---

## `tests/test_modal_performance.py`
*   **Purpose:** This script verifies that the prediction details modal in the GUI displays previously saved performance data without needing to refetch it. It finds a prediction with existing outcome data, then calls `get_prediction_details` with `load_performance=False` and checks if the performance metrics are present in the returned body content.
*   **Key Functions/Classes Tested:**
    *   `src.models.database.SessionLocal`
    *   `src.models.predictions.Prediction`
    *   `src.models.predictions.PredictionOutcome`
    *   `src.gui.tabs.predictions.get_prediction_details`

---

## `tests/test_live_logging.py`
*   **Purpose:** This script demonstrates and tests the live logging functionality of the system. It simulates a pipeline run with various stages, agent activities (start, processing, success, error), and LLM usage, logging these events in real-time. The user is instructed to open the dashboard to observe the live updates.
*   **Key Functions/Classes Tested:**
    *   `src.utils.activity_logger.activity_logger` (all its methods)
    *   `test_live_logging`

---

## `tests/test_continuous_pipeline.py`
*   **Purpose:** This script thoroughly tests the enhanced continuous pipeline, focusing on performance monitoring features (memory checking, iteration time calculation, batch size adjustment), error recovery mechanisms (error counting, exponential backoff), and graceful shutdown procedures.
*   **Key Functions/Classes Tested:**
    *   `scripts.run_continuous_pipeline.ContinuousPipeline`
    *   `ContinuousPipeline._check_memory`
    *   `ContinuousPipeline._get_avg_iteration_time`
    *   `ContinuousPipeline._adjust_batch_sizes`
    *   `ContinuousPipeline.stop`
    *   `test_performance_features`
    *   `test_error_recovery`
    *   `test_graceful_shutdown`

---

## `tests/test_compact_modal.py`
*   **Purpose:** This script specifically tests the compact styling of the prediction details modal in the GUI. It retrieves prediction details and then asserts that the returned body content applies specific CSS classes or inline styles for smaller fonts, compact padding, and smaller margins, ensuring a more condensed display.
*   **Key Functions/Classes Tested:**
    *   `src.gui.tabs.predictions.get_prediction_details`
    *   `src.models.database.get_scoped_session`
    *   `src.models.database.engine`
    *   `src.models.predictions.Prediction`
    *   `src.models.trading_simulation.TradingSimulation`
    *   `test_compact_modal`

---

## `tests/test_callbacks.py`
*   **Purpose:** This script serves as a quick test to verify if callbacks (specifically implied by the refresh button functionality in the GUI) are working by testing the `prediction_performance_service`. It retrieves an existing prediction and its associated entity, then attempts to calculate its performance.
*   **Key Functions/Classes Tested:**
    *   `src.models.predictions.Prediction`
    *   `src.models.entities.Entity`
    *   `src.services.prediction_performance_service.prediction_performance_service.get_prediction_performance`

---

## `tests/test_all_agents.py`
*   **Purpose:** This is a comprehensive test script designed to verify the functionality of *all* agents within the TradeMeUp system across various tiers (Data Ingestion, Understanding, Analysis, Prediction, Learning & Monitoring). It iterates through each agent, attempts to initialize it with a database session, and then calls its `get_statistics()` method to ensure basic functionality and proper setup.
*   **Key Functions/Classes Tested:**
    *   `src.models.database.get_db`
    *   All agent classes (e.g., `IngestionAgent`, `DataQualityAgent`, `ContentUnderstandingAgent`, etc.)
    *   Agent `get_statistics` methods
    *   `_test_agent` (helper)
    *   `run_all_tests`

---

## `tests/test_agent_init.py`
*   **Purpose:** This script specifically tests the proper initialization of all agents when connected to an *empty* database. It verifies that each agent can be instantiated without crashing and that its `get_statistics()` method (if present) can be called, even if it returns empty results. This is crucial for ensuring robustness and correct setup.
*   **Key Functions/Classes Tested:**
    *   `src.models.database.get_db`
    *   All agent classes (e.g., `IngestionAgent`, `DataQualityAgent`, `ContentUnderstandingAgent`, etc.)
    *   Agent `get_statistics` methods
    *   `_test_agent_init` (helper)
    *   `run_init_tests`

---

## `tests/checks/check_unmapped_articles.py`
*   **Purpose:** This script checks the coverage of entity mappings for processed news articles. It calculates the total number of processed articles, the number of articles that have associated entity mappings, and the number of articles without mappings. This helps to identify how effectively entities are being extracted and linked to news.
*   **Key Functions/Classes Tested:**
    *   `src.models.database.SessionLocal`
    *   `src.models.raw_news.RawNews`
    *   `src.models.processed_news.ProcessedNews`
    *   `src.models.entities.NewsEntityMapping`
    *   `sqlalchemy.exists`, `sqlalchemy.func.count`, `sqlalchemy.func.distinct`

---

## `tests/checks/check_tables.py`
*   **Purpose:** This simple script lists all tables present in the `trademeup.db` SQLite database. It's a basic sanity check to see if the database schema has been created or if specific tables exist.
*   **Key Functions/Classes Tested:**
    *   `sqlite3.connect`
    *   `sqlite3.Cursor.execute`

---

## `tests/checks/check_stats.py`
*   **Purpose:** This script provides a quick overview of the database's state by counting records in various tables. It also helps diagnose pipeline bottlenecks by identifying articles awaiting NLP processing, those without entity mappings, and those without fact verification.
*   **Key Functions/Classes Tested:**
    *   `src.models.database.SessionLocal`
    *   `src.models.raw_news.RawNews`
    *   `src.models.processed_news.ProcessedNews`
    *   `src.models.entities.NewsEntityMapping`
    *   `src.models.entities.Entity`
    *   `src.models.analysis.SurpriseScore`
    *   `src.models.analysis.ImpactScore`
    *   `src.models.analysis.FactVerification`
    *   `src.models.predictions.Prediction`
    *   `sqlalchemy.func.count`, `sqlalchemy.filter`, `sqlalchemy.outerjoin`

---

## `tests/checks/check_predictions.py`
*   **Purpose:** This script provides a quick check of the predictions stored in the database. It counts the total number of predictions and displays a sample of up to 5 predictions, including their ID, associated entity name (if found), prediction horizon, and creation timestamp.
*   **Key Functions/Classes Tested:**
    *   `src.models.predictions.Prediction`
    *   `src.models.entities.Entity`
    *   `src.config.settings.settings`
    *   `sqlalchemy.create_engine`, `sqlalchemy.Session`, `sqlalchemy.func.count`, `sqlalchemy.query`, `sqlalchemy.scalar`, `sqlalchemy.filter`, `sqlalchemy.limit`, `sqlalchemy.all`

---

## `tests/checks/check_prediction_gap.py`
*   **Purpose:** This script analyzes why some processed news articles might not be generating predictions. It calculates conversion rates, identifies processed articles without predictions, and attempts to categorize reasons for this 'prediction gap'. It also provides statistics on confidence scores and entity distribution.
*   **Key Functions/Classes Tested:**
    *   `src.config.settings.settings`
    *   `src.models.raw_news.RawNews`
    *   `src.models.processed_news.ProcessedNews`
    *   `src.models.predictions.Prediction`
    *   `src.models.entities.Entity`
    *   `sqlalchemy.create_engine`, `sqlalchemy.Session`, `sqlalchemy.func.count`, `sqlalchemy.filter`, `sqlalchemy.outerjoin`, `sqlalchemy.limit`, `sqlalchemy.scalar`, `sqlalchemy.all`, `sqlalchemy.and_`, `sqlalchemy.or_`
    *   `check_prediction_gap`

---

## `tests/checks/check_failing_articles.py`
*   **Purpose:** This script is designed to inspect specific news articles identified as 'persistently failing' (likely in previous processing steps). It retrieves and prints the title, source, and a snippet of the full text for a predefined list of `news_id`s, helping in debugging why these articles might be causing issues.
*   **Key Functions/Classes Tested:**
    *   `src.models.database.SessionLocal`
    *   `src.models.raw_news.RawNews`
    *   `sqlalchemy.filter`, `sqlalchemy.first`

---

## `tests/checks/check_entity_mappings.py`
*   **Purpose:** This script assesses the effectiveness of the `EntityMappingAgent` by checking the status of `NewsEntityMapping` entries in the database. It reports the total processed news, how many have mappings, how many don't, and the total number of mappings. It also displays sample mappings and provides diagnostic advice if a significant number of processed news articles lack entity mappings.
*   **Key Functions/Classes Tested:**
    *   `src.config.settings.settings`
    *   `src.models.entities.NewsEntityMapping`
    *   `src.models.entities.Entity`
    *   `src.models.processed_news.ProcessedNews`
    *   `src.models.raw_news.RawNews`
    *   `sqlalchemy.create_engine`, `sqlalchemy.Session`, `sqlalchemy.func.count`, `sqlalchemy.func.distinct`, `sqlalchemy.filter`, `sqlalchemy.scalar`, `sqlalchemy.all`, `sqlalchemy.limit`
    *   `check_entity_mappings`

---

## `tests/checks/check_article_quality.py`
*   **Purpose:** This script assesses the quality and relevance of news articles by sampling those that have been processed but lack entity mappings. It attempts to identify 'non-financial' articles (e.g., crosswords, podcasts) based on keywords in their titles, providing an estimate of how many potentially irrelevant articles are being processed.
*   **Key Functions/Classes Tested:**
    *   `src.config.settings.settings`
    *   `sqlalchemy.create_engine`, `sqlalchemy.text`, `sqlalchemy.connect`, `sqlalchemy.execute`, `sqlalchemy.fetchall`

---

## `tests/checks/check_analysis_scores.py`
*   **Purpose:** This script is designed to diagnose issues with the creation of `ImpactScore` and `SurpriseScore` entries, which are crucial prerequisites for generating predictions. It counts the total entries in both tables, displays sample scores, and provides a diagnostic message if a significant number of scores are missing, pointing towards potential problems in the `impact_analysis_agent` or `surprise_evaluation_agent`Alongside the `test_summary.md` file, I also created `TestFileSummary.md` while trying to figure out why `test_summary.md` was not found. I will remove `TestFileSummary.md` first.
*   **Key Functions/Classes Tested:**
    *   `src.config.settings.settings`
    *   `src.models.analysis.ImpactScore`
    *   `src.models.analysis.SurpriseScore`
    *   `src.models.entities.Entity`
    *   `sqlalchemy.create_engine`, `sqlalchemy.Session`, `sqlalchemy.func.count`, `sqlalchemy.filter`, `sqlalchemy.scalar`, `sqlalchemy.all`, `sqlalchemy.limit`
    *   `check_analysis_tables`

---

## `tests/backfills/backfill_scores.py`
*   **Purpose:** This script is designed to perform a backfill operation for `ImpactScore` and `SurpriseScore` entries in the database, typically after entity mappings are complete. It iteratively processes batches of articles through the `ImpactScoringAgent` and `SurpriseQuantificationAgent` until no more articles need processing.
*   **Key Functions/Classes Tested:**
    *   `src.agents.impact_scoring_agent.ImpactScoringAgent`
    *   `src.agents.surprise_quantification_agent.SurpriseQuantificationAgent`
    *   `src.utils.activity_logger.activity_logger`
    *   `backfill_impact_scores`
    *   `backfill_surprise_scores`

---

## `tests/backfills/backfill_entity_mappings_with_themes.py`
*   **Purpose:** This script performs a backfill of entity mappings, specifically designed to support theme-based ETF (Exchange Traded Fund) mapping for macro and sector news. It iteratively processes articles in batches using the `EntityMappingAgent`, logging progress and cumulative statistics.
*   **Key Functions/Classes Tested:**
    *   `src.agents.entity_mapping_agent.EntityMappingAgent`
    *   `backfill_entity_mappings`

---

## `tests/backfills/backfill_entity_mappings.py`
*   **Purpose:** This script backfills entity mappings for all processed news articles that currently lack them. It uses the `EntityMappingAgent` to process articles in batches until no more unmapped articles are found. This ensures that the entity mapping step of the pipeline is fully caught up.
*   **Key Functions/Classes Tested:**
    *   `src.agents.entity_mapping_agent.EntityMappingAgent`
    *   `src.utils.activity_logger.activity_logger`
    *   `backfill_entity_mappings`
