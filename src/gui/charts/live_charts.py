"""
Live Chart Components
Modular chart components for real-time market data visualization
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime, timedelta


def create_candlestick_chart(df: pd.DataFrame, symbol: str, title: str = "") -> go.Figure:
    """
    Create a candlestick chart with volume
    
    Args:
        df: DataFrame with OHLCV data
        symbol: Stock ticker symbol
        title: Chart title
        
    Returns:
        Plotly Figure
    """
    if df is None or df.empty:
        return create_empty_chart("No data available")
    
    # Create subplots: candlestick + volume
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=(title or f'{symbol} Price', 'Volume'),
        row_heights=[0.7, 0.3]
    )
    
    # Candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name='Price',
            increasing_line_color='#00ff88',
            decreasing_line_color='#ff4444'
        ),
        row=1, col=1
    )
    
    # Volume bars
    colors = ['#00ff88' if close >= open_ else '#ff4444' 
              for close, open_ in zip(df['Close'], df['Open'])]
    
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df['Volume'],
            name='Volume',
            marker_color=colors,
            showlegend=False
        ),
        row=2, col=1
    )
    
    # Update layout
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(10,10,10,1)',
        xaxis_rangeslider_visible=False,
        height=None,  # Allow dynamic height
        autosize=True,
        margin=dict(l=50, r=50, t=50, b=50),
        hovermode='x unified',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    # Update axes
    fig.update_xaxes(
        gridcolor='#333',
        showgrid=True,
        zeroline=False
    )
    
    fig.update_yaxes(
        gridcolor='#333',
        showgrid=True,
        zeroline=False
    )
    
    return fig


def create_line_chart(df: pd.DataFrame, symbol: str, column: str = 'Close') -> go.Figure:
    """
    Create a line chart for price movement
    
    Args:
        df: DataFrame with price data
        symbol: Stock ticker symbol
        column: Column to plot
        
    Returns:
        Plotly Figure
    """
    if df is None or df.empty:
        return create_empty_chart("No data available")
    
    fig = go.Figure()
    
    # Add line
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df[column],
        mode='lines',
        name=symbol,
        line=dict(color='#00d9ff', width=2),
        fill='tonexty',
        fillcolor='rgba(0, 217, 255, 0.1)'
    ))
    
    # Update layout
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(10,10,10,1)',
        title=f'{symbol} {column}',
        height=None,  # Allow dynamic height
        autosize=True,
        margin=dict(l=50, r=50, t=50, b=50),
        hovermode='x unified',
        xaxis=dict(gridcolor='#333', showgrid=True),
        yaxis=dict(gridcolor='#333', showgrid=True)
    )
    
    return fig


def create_multi_line_chart(data_dict: dict, title: str = "Comparison") -> go.Figure:
    """
    Create multi-line chart for comparing multiple stocks
    
    Args:
        data_dict: Dict mapping symbol to DataFrame
        title: Chart title
        
    Returns:
        Plotly Figure
    """
    fig = go.Figure()
    
    colors = ['#00d9ff', '#00ff88', '#ffaa00', '#ff4444', '#00aaff']
    
    for idx, (symbol, df) in enumerate(data_dict.items()):
        if df is not None and not df.empty:
            fig.add_trace(go.Scatter(
                x=df.index,
                y=df['Close'],
                mode='lines',
                name=symbol,
                line=dict(color=colors[idx % len(colors)], width=2)
            ))
    
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(10,10,10,1)',
        title=title,
        height=None,  # Allow dynamic height
        autosize=True,
        margin=dict(l=50, r=50, t=50, b=50),
        hovermode='x unified',
        xaxis=dict(gridcolor='#333', showgrid=True),
        yaxis=dict(gridcolor='#333', showgrid=True),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    return fig


def create_price_indicator_card(quote_data: dict) -> dict:
    """
    Create data for price indicator card
    
    Args:
        quote_data: Quote data from market_data provider
        
    Returns:
        Dict with formatted data
    """
    if not quote_data:
        return {
            'symbol': 'N/A',
            'price': '0.00',
            'change': '0.00',
            'change_percent': '0.00',
            'color': 'secondary'
        }
    
    change = quote_data.get('change', 0)
    color = 'success' if change >= 0 else 'danger'
    
    return {
        'symbol': quote_data['symbol'],
        'name': quote_data.get('name', quote_data['symbol']),
        'price': f"${quote_data['price']:.2f}",
        'change': f"{change:+.2f}",
        'change_percent': f"{quote_data.get('change_percent', 0):+.2f}%",
        'volume': f"{quote_data.get('volume', 0):,}",
        'market_cap': f"${quote_data.get('market_cap', 0) / 1e9:.2f}B",
        'high': f"${quote_data.get('high', 0):.2f}",
        'low': f"${quote_data.get('low', 0):.2f}",
        'color': color
    }


def create_empty_chart(message: str = "No data available") -> go.Figure:
    """
    Create empty chart with message
    
    Args:
        message: Message to display
        
    Returns:
        Plotly Figure
    """
    fig = go.Figure()
    
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=16, color="#666")
    )
    
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(10,10,10,1)',
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=None,  # Allow dynamic height
        autosize=True
    )
    
    return fig


def create_heatmap(data: pd.DataFrame, title: str = "Correlation Heatmap") -> go.Figure:
    """
    Create correlation heatmap
    
    Args:
        data: DataFrame with correlation data
        title: Chart title
        
    Returns:
        Plotly Figure
    """
    fig = go.Figure(data=go.Heatmap(
        z=data.values,
        x=data.columns,
        y=data.columns,
        colorscale='RdYlGn',
        zmid=0
    ))
    
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(10,10,10,1)',
        title=title,
        height=None,  # Allow dynamic height
        autosize=True,
        margin=dict(l=100, r=50, t=100, b=100)
    )
    
    return fig
