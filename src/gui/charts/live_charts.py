"""
Live Chart Components
Modular chart components for real-time market data visualization
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime, timedelta


def create_candlestick_chart(df: pd.DataFrame, symbol: str, title: str = "", show_volume: bool = True, show_ma: bool = False) -> go.Figure:
    """
    Create a candlestick chart with optional volume and indicators
    
    Args:
        df: DataFrame with OHLCV data
        symbol: Stock ticker symbol
        title: Chart title
        show_volume: Show volume subplot
        show_ma: Show moving averages (20, 50)
        
    Returns:
        Plotly Figure
    """
    if df is None or df.empty:
        return create_empty_chart("No data available")
    
    # Create subplots based on options
    if show_volume:
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.02,
            subplot_titles=(title or f'{symbol} Price', 'Volume'),
            row_heights=[0.75, 0.25]
        )
        volume_row = 2
    else:
        fig = go.Figure()
        volume_row = None
    
    # Candlestick chart
    candlestick = go.Candlestick(
        x=df.index,
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        name='Price',
        increasing_line_color='#00ff88',
        decreasing_line_color='#ff4444',
        increasing_fillcolor='rgba(0, 255, 136, 0.3)',
        decreasing_fillcolor='rgba(255, 68, 68, 0.3)'
    )
    
    if show_volume:
        fig.add_trace(candlestick, row=1, col=1)
    else:
        fig.add_trace(candlestick)
    
    # Add moving averages if requested
    if show_ma and len(df) >= 50:
        ma20 = df['Close'].rolling(window=20).mean()
        ma50 = df['Close'].rolling(window=50).mean()
        
        ma20_trace = go.Scatter(
            x=df.index,
            y=ma20,
            name='MA 20',
            line=dict(color='#ffa500', width=1.5),
            opacity=0.7
        )
        ma50_trace = go.Scatter(
            x=df.index,
            y=ma50,
            name='MA 50',
            line=dict(color='#00bfff', width=1.5),
            opacity=0.7
        )
        
        if show_volume:
            fig.add_trace(ma20_trace, row=1, col=1)
            fig.add_trace(ma50_trace, row=1, col=1)
        else:
            fig.add_trace(ma20_trace)
            fig.add_trace(ma50_trace)
    
    # Volume bars
    if show_volume:
        colors = ['#00ff88' if close >= open_ else '#ff4444' 
                  for close, open_ in zip(df['Close'], df['Open'])]
        
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df['Volume'],
                name='Volume',
                marker_color=colors,
                showlegend=False,
                opacity=0.7
            ),
            row=volume_row, col=1
        )
    
    # Update layout with modern styling
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(10,10,10,1)',
        xaxis_rangeslider_visible=False,
        height=None,  # Auto height
        autosize=True,  # Enable autosizing
        margin=dict(l=40, r=15, t=15, b=5, autoexpand=True),
        hovermode='x unified',
        hoverlabel=dict(
            bgcolor="rgba(30, 30, 30, 0.95)",
            font_size=13,
            font_family="monospace"
        ),
        showlegend=False,  # Hide legend completely
        font=dict(
            family="Arial, sans-serif",
            size=12,
            color="#e0e0e0"
        ),
        uirevision='constant'  # Maintain UI state on resize
    )
    
    # Update axes - hide x-axis labels, show only in hover
    fig.update_xaxes(
        gridcolor='#333',
        showgrid=True,
        zeroline=False,
        type='category',  # Uniform spacing between all data points
        showticklabels=False  # Hide timestamp labels on x-axis
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
