"""Agent package helpers.

Agents are in the middle of a migration: the older ones take a database
session in their constructor, while the converted ones open their own scoped
session per operation and take no arguments at all.

Callers used to track that split by hand - a literal list of "refactored"
agent names in the GUI, another set of assumptions in the backfill script, and
a third in the test suite. Those lists went stale every time an agent was
converted, and passing a session to an agent that no longer wants one raises
TypeError at call time.

Ask the constructor instead.
"""
import inspect

# Constructor parameter names that mean "a database session".
_SESSION_PARAM_NAMES = frozenset({"db", "session", "db_session"})


def wants_db_session(agent_class) -> bool:
    """Whether ``agent_class`` takes a database session as its first argument."""
    try:
        parameters = list(inspect.signature(agent_class.__init__).parameters.values())
    except (TypeError, ValueError):
        # Builtin or otherwise unintrospectable __init__; assume no session.
        return False

    # Skip `self`. A session, where wanted, is always the first real argument.
    for parameter in parameters[1:]:
        if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
            continue
        return parameter.name in _SESSION_PARAM_NAMES

    return False


def build_agent(agent_class, db=None):
    """Construct an agent, passing ``db`` only if its constructor wants one."""
    if db is not None and wants_db_session(agent_class):
        return agent_class(db)
    return agent_class()


__all__ = ["build_agent", "wants_db_session"]
