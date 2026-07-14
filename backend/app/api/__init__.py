"""
API路由模块
"""

from flask import Blueprint

relasim_bp = Blueprint('relasim', __name__)

from . import relasim  # noqa: E402, F401
