#!/usr/bin/env python3
"""
Sports command for the MeshCore Bot
Provides sports scores and schedules using ESPN API
API description via https://github.com/zuplo/espn-openapi/
"""

import re
import json
import requests
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from .base_command import BaseCommand
from ..models import MeshMessage


class SportsCommand(BaseCommand):
    """Handles sports commands with ESPN API integration"""
    
    # Plugin metadata
    name = "sports"
    keywords = ['sports', 'score', 'scores']
    description = "Get sports scores and schedules (usage: sports [team/league])"
    category = "sports"
    cooldown_seconds = 3  # 3 second cooldown per user to prevent API abuse
    
    # ESPN API base URL
    ESPN_BASE_URL = "http://site.api.espn.com/apis/site/v2/sports"
    
    # Sport emojis for easy identification
    SPORT_EMOJIS = {
        'football': '🏈',
        'baseball': '⚾',
        'basketball': '🏀',
        'hockey': '🏒',
        'soccer': '⚽'
    }
    
    # Team mappings for common searches
    TEAM_MAPPINGS = {
        # NFL Teams
        'seahawks': {'sport': 'football', 'league': 'nfl', 'team_id': '26'},
        'hawks': {'sport': 'football', 'league': 'nfl', 'team_id': '26'},
        '49ers': {'sport': 'football', 'league': 'nfl', 'team_id': '25'},
        'niners': {'sport': 'football', 'league': 'nfl', 'team_id': '25'},
        'sf': {'sport': 'football', 'league': 'nfl', 'team_id': '25'},
        'bears': {'sport': 'football', 'league': 'nfl', 'team_id': '3'},
        'chicago': {'sport': 'football', 'league': 'nfl', 'team_id': '3'},
        'chi': {'sport': 'football', 'league': 'nfl', 'team_id': '3'},
        'bengals': {'sport': 'football', 'league': 'nfl', 'team_id': '4'},
        'cincinnati': {'sport': 'football', 'league': 'nfl', 'team_id': '4'},
        'cin': {'sport': 'football', 'league': 'nfl', 'team_id': '4'},
        'bills': {'sport': 'football', 'league': 'nfl', 'team_id': '2'},
        'buffalo': {'sport': 'football', 'league': 'nfl', 'team_id': '2'},
        'buf': {'sport': 'football', 'league': 'nfl', 'team_id': '2'},
        'broncos': {'sport': 'football', 'league': 'nfl', 'team_id': '7'},
        'denver': {'sport': 'football', 'league': 'nfl', 'team_id': '7'},
        'den': {'sport': 'football', 'league': 'nfl', 'team_id': '7'},
        'browns': {'sport': 'football', 'league': 'nfl', 'team_id': '5'},
        'cleveland': {'sport': 'football', 'league': 'nfl', 'team_id': '5'},
        'cle': {'sport': 'football', 'league': 'nfl', 'team_id': '5'},
        'buccaneers': {'sport': 'football', 'league': 'nfl', 'team_id': '27'},
        'bucs': {'sport': 'football', 'league': 'nfl', 'team_id': '27'},
        'tampa bay': {'sport': 'football', 'league': 'nfl', 'team_id': '27'},
        'tb': {'sport': 'football', 'league': 'nfl', 'team_id': '27'},
        'cardinals': {'sport': 'football', 'league': 'nfl', 'team_id': '22'},
        'arizona': {'sport': 'football', 'league': 'nfl', 'team_id': '22'},
        'ari': {'sport': 'football', 'league': 'nfl', 'team_id': '22'},
        'chargers': {'sport': 'football', 'league': 'nfl', 'team_id': '24'},
        'lac': {'sport': 'football', 'league': 'nfl', 'team_id': '24'},
        'chiefs': {'sport': 'football', 'league': 'nfl', 'team_id': '12'},
        'kansas city': {'sport': 'football', 'league': 'nfl', 'team_id': '12'},
        'kc': {'sport': 'football', 'league': 'nfl', 'team_id': '12'},
        'colts': {'sport': 'football', 'league': 'nfl', 'team_id': '11'},
        'indianapolis': {'sport': 'football', 'league': 'nfl', 'team_id': '11'},
        'ind': {'sport': 'football', 'league': 'nfl', 'team_id': '11'},
        'commanders': {'sport': 'football', 'league': 'nfl', 'team_id': '28'},
        'washington': {'sport': 'football', 'league': 'nfl', 'team_id': '28'},
        'wsh': {'sport': 'football', 'league': 'nfl', 'team_id': '28'},
        'cowboys': {'sport': 'football', 'league': 'nfl', 'team_id': '6'},
        'dallas': {'sport': 'football', 'league': 'nfl', 'team_id': '6'},
        'dal': {'sport': 'football', 'league': 'nfl', 'team_id': '6'},
        'dolphins': {'sport': 'football', 'league': 'nfl', 'team_id': '15'},
        'miami': {'sport': 'football', 'league': 'nfl', 'team_id': '15'},
        'mia': {'sport': 'football', 'league': 'nfl', 'team_id': '15'},
        'eagles': {'sport': 'football', 'league': 'nfl', 'team_id': '21'},
        'philadelphia': {'sport': 'football', 'league': 'nfl', 'team_id': '21'},
        'phi': {'sport': 'football', 'league': 'nfl', 'team_id': '21'},
        'falcons': {'sport': 'football', 'league': 'nfl', 'team_id': '1'},
        'atlanta': {'sport': 'football', 'league': 'nfl', 'team_id': '1'},
        'atl': {'sport': 'football', 'league': 'nfl', 'team_id': '1'},
        'giants': {'sport': 'football', 'league': 'nfl', 'team_id': '19'},
        'nyg': {'sport': 'football', 'league': 'nfl', 'team_id': '19'},
        'jaguars': {'sport': 'football', 'league': 'nfl', 'team_id': '30'},
        'jax': {'sport': 'football', 'league': 'nfl', 'team_id': '30'},
        'jets': {'sport': 'football', 'league': 'nfl', 'team_id': '20'},
        'nyj': {'sport': 'football', 'league': 'nfl', 'team_id': '20'},
        'lions': {'sport': 'football', 'league': 'nfl', 'team_id': '8'},
        'detroit': {'sport': 'football', 'league': 'nfl', 'team_id': '8'},
        'det': {'sport': 'football', 'league': 'nfl', 'team_id': '8'},
        'packers': {'sport': 'football', 'league': 'nfl', 'team_id': '9'},
        'green bay': {'sport': 'football', 'league': 'nfl', 'team_id': '9'},
        'gb': {'sport': 'football', 'league': 'nfl', 'team_id': '9'},
        'panthers': {'sport': 'football', 'league': 'nfl', 'team_id': '29'},
        'carolina': {'sport': 'football', 'league': 'nfl', 'team_id': '29'},
        'car': {'sport': 'football', 'league': 'nfl', 'team_id': '29'},
        'patriots': {'sport': 'football', 'league': 'nfl', 'team_id': '17'},
        'new england': {'sport': 'football', 'league': 'nfl', 'team_id': '17'},
        'ne': {'sport': 'football', 'league': 'nfl', 'team_id': '17'},
        'raiders': {'sport': 'football', 'league': 'nfl', 'team_id': '13'},
        'las vegas': {'sport': 'football', 'league': 'nfl', 'team_id': '13'},
        'lv': {'sport': 'football', 'league': 'nfl', 'team_id': '13'},
        'rams': {'sport': 'football', 'league': 'nfl', 'team_id': '14'},
        'lar': {'sport': 'football', 'league': 'nfl', 'team_id': '14'},
        'ravens': {'sport': 'football', 'league': 'nfl', 'team_id': '33'},
        'baltimore': {'sport': 'football', 'league': 'nfl', 'team_id': '33'},
        'bal': {'sport': 'football', 'league': 'nfl', 'team_id': '33'},
        'saints': {'sport': 'football', 'league': 'nfl', 'team_id': '18'},
        'new orleans': {'sport': 'football', 'league': 'nfl', 'team_id': '18'},
        'no': {'sport': 'football', 'league': 'nfl', 'team_id': '18'},
        'steelers': {'sport': 'football', 'league': 'nfl', 'team_id': '23'},
        'pittsburgh': {'sport': 'football', 'league': 'nfl', 'team_id': '23'},
        'pit': {'sport': 'football', 'league': 'nfl', 'team_id': '23'},
        'texans': {'sport': 'football', 'league': 'nfl', 'team_id': '34'},
        'houston': {'sport': 'football', 'league': 'nfl', 'team_id': '34'},
        'hou': {'sport': 'football', 'league': 'nfl', 'team_id': '34'},
        'titans': {'sport': 'football', 'league': 'nfl', 'team_id': '10'},
        'tennessee': {'sport': 'football', 'league': 'nfl', 'team_id': '10'},
        'ten': {'sport': 'football', 'league': 'nfl', 'team_id': '10'},
        'vikings': {'sport': 'football', 'league': 'nfl', 'team_id': '16'},
        'minnesota': {'sport': 'football', 'league': 'nfl', 'team_id': '16'},
        'min': {'sport': 'football', 'league': 'nfl', 'team_id': '16'},
        
        # MLB Teams
        'mariners': {'sport': 'baseball', 'league': 'mlb', 'team_id': '12'},
        'seattle': {'sport': 'baseball', 'league': 'mlb', 'team_id': '12'},
        'sea': {'sport': 'baseball', 'league': 'mlb', 'team_id': '12'},
        'angels': {'sport': 'baseball', 'league': 'mlb', 'team_id': '3'},
        'laa': {'sport': 'baseball', 'league': 'mlb', 'team_id': '3'},
        'astros': {'sport': 'baseball', 'league': 'mlb', 'team_id': '18'},
        'houston': {'sport': 'baseball', 'league': 'mlb', 'team_id': '18'},
        'hou': {'sport': 'baseball', 'league': 'mlb', 'team_id': '18'},
        'athletics': {'sport': 'baseball', 'league': 'mlb', 'team_id': '11'},
        'a\'s': {'sport': 'baseball', 'league': 'mlb', 'team_id': '11'},
        'oakland': {'sport': 'baseball', 'league': 'mlb', 'team_id': '11'},
        'oak': {'sport': 'baseball', 'league': 'mlb', 'team_id': '11'},
        'blue jays': {'sport': 'baseball', 'league': 'mlb', 'team_id': '14'},
        'toronto': {'sport': 'baseball', 'league': 'mlb', 'team_id': '14'},
        'tor': {'sport': 'baseball', 'league': 'mlb', 'team_id': '14'},
        'braves': {'sport': 'baseball', 'league': 'mlb', 'team_id': '15'},
        'atlanta': {'sport': 'baseball', 'league': 'mlb', 'team_id': '15'},
        'atl': {'sport': 'baseball', 'league': 'mlb', 'team_id': '15'},
        'brewers': {'sport': 'baseball', 'league': 'mlb', 'team_id': '8'},
        'milwaukee': {'sport': 'baseball', 'league': 'mlb', 'team_id': '8'},
        'mil': {'sport': 'baseball', 'league': 'mlb', 'team_id': '8'},
        'cardinals': {'sport': 'baseball', 'league': 'mlb', 'team_id': '24'},
        'st louis': {'sport': 'baseball', 'league': 'mlb', 'team_id': '24'},
        'stl': {'sport': 'baseball', 'league': 'mlb', 'team_id': '24'},
        'cubs': {'sport': 'baseball', 'league': 'mlb', 'team_id': '16'},
        'chicago': {'sport': 'baseball', 'league': 'mlb', 'team_id': '16'},
        'chc': {'sport': 'baseball', 'league': 'mlb', 'team_id': '16'},
        'diamondbacks': {'sport': 'baseball', 'league': 'mlb', 'team_id': '29'},
        'arizona': {'sport': 'baseball', 'league': 'mlb', 'team_id': '29'},
        'ari': {'sport': 'baseball', 'league': 'mlb', 'team_id': '29'},
        'dodgers': {'sport': 'baseball', 'league': 'mlb', 'team_id': '19'},
        'lad': {'sport': 'baseball', 'league': 'mlb', 'team_id': '19'},
        'giants': {'sport': 'baseball', 'league': 'mlb', 'team_id': '26'},
        'san francisco': {'sport': 'baseball', 'league': 'mlb', 'team_id': '26'},
        'sf': {'sport': 'baseball', 'league': 'mlb', 'team_id': '26'},
        'guardians': {'sport': 'baseball', 'league': 'mlb', 'team_id': '5'},
        'cleveland': {'sport': 'baseball', 'league': 'mlb', 'team_id': '5'},
        'cle': {'sport': 'baseball', 'league': 'mlb', 'team_id': '5'},
        'marlins': {'sport': 'baseball', 'league': 'mlb', 'team_id': '28'},
        'miami': {'sport': 'baseball', 'league': 'mlb', 'team_id': '28'},
        'mia': {'sport': 'baseball', 'league': 'mlb', 'team_id': '28'},
        'mets': {'sport': 'baseball', 'league': 'mlb', 'team_id': '21'},
        'nym': {'sport': 'baseball', 'league': 'mlb', 'team_id': '21'},
        'nationals': {'sport': 'baseball', 'league': 'mlb', 'team_id': '20'},
        'washington': {'sport': 'baseball', 'league': 'mlb', 'team_id': '20'},
        'was': {'sport': 'baseball', 'league': 'mlb', 'team_id': '20'},
        'orioles': {'sport': 'baseball', 'league': 'mlb', 'team_id': '1'},
        'baltimore': {'sport': 'baseball', 'league': 'mlb', 'team_id': '1'},
        'bal': {'sport': 'baseball', 'league': 'mlb', 'team_id': '1'},
        'padres': {'sport': 'baseball', 'league': 'mlb', 'team_id': '25'},
        'san diego': {'sport': 'baseball', 'league': 'mlb', 'team_id': '25'},
        'sd': {'sport': 'baseball', 'league': 'mlb', 'team_id': '25'},
        'phillies': {'sport': 'baseball', 'league': 'mlb', 'team_id': '22'},
        'philadelphia': {'sport': 'baseball', 'league': 'mlb', 'team_id': '22'},
        'phi': {'sport': 'baseball', 'league': 'mlb', 'team_id': '22'},
        'pirates': {'sport': 'baseball', 'league': 'mlb', 'team_id': '23'},
        'pittsburgh': {'sport': 'baseball', 'league': 'mlb', 'team_id': '23'},
        'pit': {'sport': 'baseball', 'league': 'mlb', 'team_id': '23'},
        'rangers': {'sport': 'baseball', 'league': 'mlb', 'team_id': '13'},
        'texas': {'sport': 'baseball', 'league': 'mlb', 'team_id': '13'},
        'tex': {'sport': 'baseball', 'league': 'mlb', 'team_id': '13'},
        'rays': {'sport': 'baseball', 'league': 'mlb', 'team_id': '30'},
        'tampa bay': {'sport': 'baseball', 'league': 'mlb', 'team_id': '30'},
        'tb': {'sport': 'baseball', 'league': 'mlb', 'team_id': '30'},
        'red sox': {'sport': 'baseball', 'league': 'mlb', 'team_id': '2'},
        'boston': {'sport': 'baseball', 'league': 'mlb', 'team_id': '2'},
        'bos': {'sport': 'baseball', 'league': 'mlb', 'team_id': '2'},
        'reds': {'sport': 'baseball', 'league': 'mlb', 'team_id': '17'},
        'cincinnati': {'sport': 'baseball', 'league': 'mlb', 'team_id': '17'},
        'cin': {'sport': 'baseball', 'league': 'mlb', 'team_id': '17'},
        'rockies': {'sport': 'baseball', 'league': 'mlb', 'team_id': '27'},
        'colorado': {'sport': 'baseball', 'league': 'mlb', 'team_id': '27'},
        'col': {'sport': 'baseball', 'league': 'mlb', 'team_id': '27'},
        'royals': {'sport': 'baseball', 'league': 'mlb', 'team_id': '7'},
        'kansas city': {'sport': 'baseball', 'league': 'mlb', 'team_id': '7'},
        'kc': {'sport': 'baseball', 'league': 'mlb', 'team_id': '7'},
        'tigers': {'sport': 'baseball', 'league': 'mlb', 'team_id': '6'},
        'detroit': {'sport': 'baseball', 'league': 'mlb', 'team_id': '6'},
        'det': {'sport': 'baseball', 'league': 'mlb', 'team_id': '6'},
        'twins': {'sport': 'baseball', 'league': 'mlb', 'team_id': '9'},
        'minnesota': {'sport': 'baseball', 'league': 'mlb', 'team_id': '9'},
        'min': {'sport': 'baseball', 'league': 'mlb', 'team_id': '9'},
        'white sox': {'sport': 'baseball', 'league': 'mlb', 'team_id': '4'},
        'chw': {'sport': 'baseball', 'league': 'mlb', 'team_id': '4'},
        'yankees': {'sport': 'baseball', 'league': 'mlb', 'team_id': '10'},
        'new york': {'sport': 'baseball', 'league': 'mlb', 'team_id': '10'},
        'nyy': {'sport': 'baseball', 'league': 'mlb', 'team_id': '10'},
        
        # NBA Teams (limited data available from API)
        'lakers': {'sport': 'basketball', 'league': 'nba', 'team_id': '13'},
        'warriors': {'sport': 'basketball', 'league': 'nba', 'team_id': '9'},
        'celtics': {'sport': 'basketball', 'league': 'nba', 'team_id': '2'},
        'heat': {'sport': 'basketball', 'league': 'nba', 'team_id': '14'},
        '76ers': {'sport': 'basketball', 'league': 'nba', 'team_id': '20'},
        'knicks': {'sport': 'basketball', 'league': 'nba', 'team_id': '18'},
        'pelicans': {'sport': 'basketball', 'league': 'nba', 'team_id': '3'},
        
        # NHL Teams (limited data available from API)
        'kraken': {'sport': 'hockey', 'league': 'nhl', 'team_id': '58'},
        'seattle kraken': {'sport': 'hockey', 'league': 'nhl', 'team_id': '58'},
        'blues': {'sport': 'hockey', 'league': 'nhl', 'team_id': '19'},
        'stars': {'sport': 'hockey', 'league': 'nhl', 'team_id': '9'},
        
        # MLS Teams
        'sounders': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '9726'},
        'seattle sounders': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '9726'},
        'atlanta united': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '18418'},
        'atl': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '18418'},
        'austin fc': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '20906'},
        'atx': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '20906'},
        'cf montreal': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '9720'},
        'montreal': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '9720'},
        'mtl': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '9720'},
        'charlotte fc': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '21300'},
        'clt': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '21300'},
        'chicago fire': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '182'},
        'fire': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '182'},
        'chi': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '182'},
        'rapids': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '184'},
        'colorado': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '184'},
        'col': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '184'},
        'crew': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '183'},
        'columbus': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '183'},
        'clb': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '183'},
        'dc united': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '193'},
        'dc': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '193'},
        'fc cincinnati': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '18267'},
        'cincinnati': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '18267'},
        'cin': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '18267'},
        'fc dallas': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '185'},
        'dallas': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '185'},
        'dal': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '185'},
        'dynamo': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '6077'},
        'houston': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '6077'},
        'hou': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '6077'},
        'inter miami': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '20232'},
        'miami': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '20232'},
        'mia': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '20232'},
        'la galaxy': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '187'},
        'galaxy': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '187'},
        'la': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '187'},
        'lafc': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '18966'},
        'minnesota united': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '17362'},
        'minnesota': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '17362'},
        'min': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '17362'},
        'nashville sc': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '18986'},
        'nashville': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '18986'},
        'nsh': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '18986'},
        'revolution': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '189'},
        'new england': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '189'},
        'ne': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '189'},
        'nyc fc': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '17606'},
        'nyc': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '17606'},
        'red bulls': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '190'},
        'ny': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '190'},
        'orlando city': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '12011'},
        'orlando': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '12011'},
        'orl': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '12011'},
        'union': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '10739'},
        'philadelphia': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '10739'},
        'phi': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '10739'},
        'timbers': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '9723'},
        'portland': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '9723'},
        'por': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '9723'},
        'real salt lake': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '4771'},
        'salt lake': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '4771'},
        'rsl': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '4771'},
        'san diego fc': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '22529'},
        'san diego': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '22529'},
        'sd': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '22529'},
        'earthquakes': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '191'},
        'san jose': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '191'},
        'sj': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '191'},
        'sporting kc': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '186'},
        'sporting kansas city': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '186'},
        'skc': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '186'},
        'st louis city': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '21812'},
        'st louis': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '21812'},
        'stl': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '21812'},
        'toronto fc': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '7318'},
        'toronto': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '7318'},
        'tor': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '7318'},
        'whitecaps': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '9727'},
        'vancouver': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '9727'},
        'van': {'sport': 'soccer', 'league': 'usa.1', 'team_id': '9727'},
        
        # Premier League Teams
        'lfc': {'sport': 'soccer', 'league': 'eng.1', 'team_id': '364'},
        'liverpool': {'sport': 'soccer', 'league': 'eng.1', 'team_id': '364'},
        'manchester united': {'sport': 'soccer', 'league': 'eng.1', 'team_id': '360'},
        'man united': {'sport': 'soccer', 'league': 'eng.1', 'team_id': '360'},
        'arsenal': {'sport': 'soccer', 'league': 'eng.1', 'team_id': '359'},
        'chelsea': {'sport': 'soccer', 'league': 'eng.1', 'team_id': '363'},
        'manchester city': {'sport': 'soccer', 'league': 'eng.1', 'team_id': '382'},
        'man city': {'sport': 'soccer', 'league': 'eng.1', 'team_id': '382'},
    }
    
    def __init__(self, bot):
        super().__init__(bot)
        self.url_timeout = 10  # seconds
        
        # Per-user cooldown tracking
        self.user_cooldowns = {}  # user_id -> last_execution_time
        
        # Load default teams from config
        self.default_teams = self.load_default_teams()
        self.sports_channels = self.load_sports_channels()
        
    def load_default_teams(self) -> List[str]:
        """Load default teams from config"""
        teams_str = self.bot.config.get('Sports', 'teams', fallback='seahawks,mariners,sounders,kraken')
        return [team.strip().lower() for team in teams_str.split(',') if team.strip()]
    
    def load_sports_channels(self) -> List[str]:
        """Load sports channels from config"""
        channels_str = self.bot.config.get('Sports', 'channels', fallback='')
        return [channel.strip() for channel in channels_str.split(',') if channel.strip()]
    
    def can_execute(self, message: MeshMessage) -> bool:
        """Check if this command can execute with the given message"""
        # Check if sports command is enabled
        sports_enabled = self.bot.config.getboolean('Sports', 'sports_enabled', fallback=True)
        if not sports_enabled:
            return False
        
        # Check if command requires DM and message is not DM
        if self.requires_dm and not message.is_dm:
            return False
        
        # Check if command requires specific channels (only for channel messages, not DMs)
        if not message.is_dm and self.sports_channels and message.channel not in self.sports_channels:
            return False
        
        # Check per-user cooldown (don't set it here, just check)
        if self.cooldown_seconds > 0:
            import time
            current_time = time.time()
            user_id = message.sender_id or "unknown"
            
            if user_id in self.user_cooldowns:
                time_since_last = current_time - self.user_cooldowns[user_id]
                if time_since_last < self.cooldown_seconds:
                    remaining = self.cooldown_seconds - time_since_last
                    self.logger.info(f"Sports command cooldown active for user {user_id}, {remaining:.1f}s remaining")
                    return False
        
        return True
    
    def get_help_text(self) -> str:
        return "Get sports scores & schedules. Use 'sports' for default teams, 'sports [team]' for specific team, or 'sports [league]' for league games."
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the sports command"""
        try:
            # Set cooldown for this user
            if self.cooldown_seconds > 0:
                import time
                current_time = time.time()
                user_id = message.sender_id or "unknown"
                self.user_cooldowns[user_id] = current_time
            
            # Parse the command
            content = message.content.strip()
            if content.startswith('!'):
                content = content[1:].strip()
            
            # Extract team name if provided
            parts = content.split()
            if len(parts) > 1:
                team_name = ' '.join(parts[1:]).lower()
                response = await self.get_team_scores(team_name)
            else:
                response = await self.get_default_teams_scores()
            
            # Send response
            return await self.send_response(message, response)
            
        except Exception as e:
            self.logger.error(f"Error in sports command: {e}")
            return await self.send_response(message, "Error fetching sports data")
    
    async def get_default_teams_scores(self) -> str:
        """Get scores for default teams, sorted by game time"""
        if not self.default_teams:
            return "No default teams configured"
        
        game_data = []
        for team in self.default_teams:
            try:
                team_info = self.TEAM_MAPPINGS.get(team)
                if team_info:
                    game_info = await self.fetch_team_game_data(team_info)
                    if game_info:
                        game_data.append(game_info)
            except Exception as e:
                self.logger.warning(f"Error fetching score for {team}: {e}")
        
        if not game_data:
            return "No games found for default teams"
        
        # Sort by game time (earliest first)
        game_data.sort(key=lambda x: x['timestamp'])
        
        # Format responses with sport emojis
        responses = []
        for game in game_data:
            sport_emoji = self.SPORT_EMOJIS.get(game['sport'], '🏆')
            responses.append(f"{sport_emoji} {game['formatted']}")
        
        # Join responses with newlines and ensure under 130 characters
        result = "\n".join(responses)
        if len(result) > 130:
            # If still too long, truncate the last response
            while len(result) > 130 and len(responses) > 1:
                responses.pop()
                result = "\n".join(responses)
            if len(result) > 130:
                result = result[:127] + "..."
        
        return result
    
    def get_league_info(self, league_name: str) -> Optional[Dict[str, str]]:
        """Get league information for league queries"""
        league_mappings = {
            # NFL
            'nfl': {'sport': 'football', 'league': 'nfl'},
            'football': {'sport': 'football', 'league': 'nfl'},
            
            # MLB
            'mlb': {'sport': 'baseball', 'league': 'mlb'},
            'baseball': {'sport': 'baseball', 'league': 'mlb'},
            
            # NBA
            'nba': {'sport': 'basketball', 'league': 'nba'},
            'basketball': {'sport': 'basketball', 'league': 'nba'},
            
            # NHL
            'nhl': {'sport': 'hockey', 'league': 'nhl'},
            'hockey': {'sport': 'hockey', 'league': 'nhl'},
            
            # MLS
            'mls': {'sport': 'soccer', 'league': 'usa.1'},
            'soccer': {'sport': 'soccer', 'league': 'usa.1'},
            
            # Premier League
            'epl': {'sport': 'soccer', 'league': 'eng.1'},
            'premier league': {'sport': 'soccer', 'league': 'eng.1'},
            'premier': {'sport': 'soccer', 'league': 'eng.1'},
        }
        
        return league_mappings.get(league_name.lower())
    
    async def get_league_scores(self, league_info: Dict[str, str]) -> str:
        """Get upcoming games for a league"""
        try:
            # Construct API URL
            url = f"{self.ESPN_BASE_URL}/{league_info['sport']}/{league_info['league']}/scoreboard"
            
            # Make API request
            response = requests.get(url, timeout=self.url_timeout)
            response.raise_for_status()
            
            data = response.json()
            events = data.get('events', [])
            
            if not events:
                return f"No games found for {league_info['sport']}"
            
            # Parse all games and sort by time
            game_data = []
            for event in events:
                game_info = self.parse_league_game_event(event, league_info['sport'])
                if game_info:
                    game_data.append(game_info)
            
            if not game_data:
                return f"No games found for {league_info['sport']}"
            
            # Sort by game time (earliest first)
            game_data.sort(key=lambda x: x['timestamp'])
            
            # Format responses with sport emojis
            responses = []
            for game in game_data[:5]:  # Limit to 5 games to keep under 130 chars
                sport_emoji = self.SPORT_EMOJIS.get(game['sport'], '🏆')
                responses.append(f"{sport_emoji} {game['formatted']}")
            
            # Join responses with newlines and ensure under 130 characters
            result = "\n".join(responses)
            if len(result) > 130:
                # If still too long, truncate the last response
                while len(result) > 130 and len(responses) > 1:
                    responses.pop()
                    result = "\n".join(responses)
                if len(result) > 130:
                    result = result[:127] + "..."
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error fetching league scores: {e}")
            return f"Error fetching {league_info['sport']} data"
    
    def parse_league_game_event(self, event: Dict, sport: str) -> Optional[Dict]:
        """Parse a league game event and return structured data with timestamp for sorting"""
        try:
            competitions = event.get('competitions', [])
            if not competitions:
                return None
            
            competition = competitions[0]
            competitors = competition.get('competitors', [])
            
            if len(competitors) != 2:
                return None
            
            # Extract team info
            team1 = competitors[0]
            team2 = competitors[1]
            
            team1_name = team1.get('team', {}).get('abbreviation', 'UNK')
            team2_name = team2.get('team', {}).get('abbreviation', 'UNK')
            
            # Get scores
            team1_score = team1.get('score', '0')
            team2_score = team2.get('score', '0')
            
            # Get game status
            status = event.get('status', {})
            status_type = status.get('type', {})
            status_name = status_type.get('name', 'UNKNOWN')
            
            # Get timestamp for sorting
            date_str = event.get('date', '')
            timestamp = 0  # Default for sorting
            if date_str:
                try:
                    dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    timestamp = dt.timestamp()
                except:
                    pass
            
            # Format based on game status
            if status_name in ['STATUS_IN_PROGRESS', 'STATUS_FIRST_HALF', 'STATUS_SECOND_HALF']:
                # Game is live - prioritize these (use negative timestamp)
                clock = status.get('displayClock', '')
                period = status.get('period', 0)
                
                # Format period based on sport
                if sport == 'baseball':
                    period_str = f"{period}I"  # Innings - no clock needed
                    formatted = f"{team1_name} {team1_score}-{team2_score} {team2_name} ({period_str})"
                elif sport == 'soccer':
                    # For soccer, use displayClock if available (e.g., "90'+5'"), otherwise use half
                    if clock and clock != '0:00' and clock != "0'":
                        period_str = clock  # Use displayClock directly (e.g., "90'+5'")
                        formatted = f"{team1_name} {team1_score}-{team2_score} {team2_name} ({period_str})"
                    else:
                        period_str = f"{period}H"  # Fallback to half
                        formatted = f"{team1_name} {team1_score}-{team2_score} {team2_name} ({clock} {period_str})"
                elif sport == 'football':
                    period_str = f"Q{period}"  # Quarters
                    formatted = f"{team1_name} {team1_score}-{team2_score} {team2_name} ({clock} {period_str})"
                else:
                    period_str = f"P{period}"  # Generic periods
                    formatted = f"{team1_name} {team1_score}-{team2_score} {team2_name} ({clock} {period_str})"
                
                timestamp = -1  # Live games first
                
            elif status_name == 'STATUS_SCHEDULED':
                # Game is scheduled
                if date_str:
                    try:
                        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        local_dt = dt.astimezone()
                        time_str = local_dt.strftime("%m/%d %I:%M %p")
                        formatted = f"{team1_name} vs {team2_name} ({time_str})"
                    except:
                        formatted = f"{team1_name} vs {team2_name} (TBD)"
                        timestamp = 9999999999  # Put TBD games last
                else:
                    formatted = f"{team1_name} vs {team2_name} (TBD)"
                    timestamp = 9999999999  # Put TBD games last
                    
            elif status_name == 'STATUS_HALFTIME':
                # Game is at halftime
                formatted = f"{team1_name} {team1_score}-{team2_score} {team2_name} (HT)"
                timestamp = -2  # Halftime games second priority after live games
            elif status_name == 'STATUS_FULL_TIME':
                # Soccer game is finished - put these last
                formatted = f"{team1_name} {team1_score}-{team2_score} {team2_name} (FT)"
                timestamp = 9999999998  # Final games second to last
            elif status_name == 'STATUS_FINAL':
                # Other sports game is finished - put these last
                formatted = f"{team1_name} {team1_score}-{team2_score} {team2_name} (F)"
                timestamp = 9999999998  # Final games second to last
                
            else:
                # Other status
                formatted = f"{team1_name} {team1_score}-{team2_score} {team2_name} ({status_name})"
                timestamp = 9999999997  # Other statuses third to last
            
            return {
                'timestamp': timestamp,
                'formatted': formatted,
                'sport': sport,
                'status': status_name
            }
                
        except Exception as e:
            self.logger.error(f"Error parsing league game event: {e}")
            return None
    
    async def get_team_scores(self, team_name: str) -> str:
        """Get scores for a specific team or league"""
        # Check if this is a league query
        league_info = self.get_league_info(team_name)
        if league_info:
            return await self.get_league_scores(league_info)
        
        # Otherwise, treat as team query
        team_info = self.TEAM_MAPPINGS.get(team_name)
        if not team_info:
            return f"Team/League '{team_name}' not found. Try: seahawks, mariners, sounders, kraken, chiefs, lfc, mlb, nfl, mls, epl, etc."
        
        try:
            score_info = await self.fetch_team_score(team_info)
            if score_info:
                # Add sport emoji to the score info
                sport_emoji = self.SPORT_EMOJIS.get(team_info['sport'], '🏆')
                return f"{sport_emoji} {score_info}"
            else:
                return f"No games found for {team_name}"
        except Exception as e:
            self.logger.error(f"Error fetching score for {team_name}: {e}")
            return f"Error fetching data for {team_name}"
    
    async def fetch_team_score(self, team_info: Dict[str, str]) -> Optional[str]:
        """Fetch score information for a team (legacy method for individual team queries)"""
        game_data = await self.fetch_team_game_data(team_info)
        return game_data['formatted'] if game_data else None
    
    async def fetch_team_game_data(self, team_info: Dict[str, str]) -> Optional[Dict]:
        """Fetch structured game data for a team with timestamp for sorting"""
        try:
            # Construct API URL
            url = f"{self.ESPN_BASE_URL}/{team_info['sport']}/{team_info['league']}/scoreboard"
            
            # Make API request
            response = requests.get(url, timeout=self.url_timeout)
            response.raise_for_status()
            
            data = response.json()
            events = data.get('events', [])
            
            if not events:
                return None
            
            # Find games involving the team
            for event in events:
                game_data = self.parse_game_event_with_timestamp(event, team_info['team_id'], team_info['sport'])
                if game_data:
                    return game_data
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error fetching team game data: {e}")
            return None
    
    def parse_game_event_with_timestamp(self, event: Dict, team_id: str, sport: str) -> Optional[Dict]:
        """Parse a game event and return structured data with timestamp for sorting"""
        try:
            competitions = event.get('competitions', [])
            if not competitions:
                return None
            
            competition = competitions[0]
            competitors = competition.get('competitors', [])
            
            if len(competitors) != 2:
                return None
            
            # Check if our team is in this game
            our_team = None
            other_team = None
            
            for competitor in competitors:
                if competitor.get('team', {}).get('id') == team_id:
                    our_team = competitor
                else:
                    other_team = competitor
            
            if not our_team or not other_team:
                return None
            
            # Extract team info
            our_team_name = our_team.get('team', {}).get('abbreviation', 'UNK')
            other_team_name = other_team.get('team', {}).get('abbreviation', 'UNK')
            
            # Get scores
            our_score = our_team.get('score', '0')
            other_score = other_team.get('score', '0')
            
            # Get game status
            status = event.get('status', {})
            status_type = status.get('type', {})
            status_name = status_type.get('name', 'UNKNOWN')
            
            # Get timestamp for sorting
            date_str = event.get('date', '')
            timestamp = 0  # Default for sorting
            if date_str:
                try:
                    dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    timestamp = dt.timestamp()
                except:
                    pass
            
            # Format based on game status
            if status_name in ['STATUS_IN_PROGRESS', 'STATUS_FIRST_HALF', 'STATUS_SECOND_HALF']:
                # Game is live - prioritize these (use negative timestamp)
                clock = status.get('displayClock', '')
                period = status.get('period', 0)
                
                # Format period based on sport
                if sport == 'baseball':
                    period_str = f"{period}I"  # Innings - no clock needed
                    formatted = f"{our_team_name} {our_score}-{other_score} {other_team_name} ({period_str})"
                elif sport == 'soccer':
                    # For soccer, use displayClock if available (e.g., "90'+5'"), otherwise use half
                    if clock and clock != '0:00' and clock != "0'":
                        period_str = clock  # Use displayClock directly (e.g., "90'+5'")
                        formatted = f"{our_team_name} {our_score}-{other_score} {other_team_name} ({period_str})"
                    else:
                        period_str = f"{period}H"  # Fallback to half
                        formatted = f"{our_team_name} {our_score}-{other_score} {other_team_name} ({clock} {period_str})"
                elif sport == 'football':
                    period_str = f"Q{period}"  # Quarters
                    formatted = f"{our_team_name} {our_score}-{other_score} {other_team_name} ({clock} {period_str})"
                else:
                    period_str = f"P{period}"  # Generic periods
                    formatted = f"{our_team_name} {our_score}-{other_score} {other_team_name} ({clock} {period_str})"
                
                timestamp = -1  # Live games first
                
            elif status_name == 'STATUS_SCHEDULED':
                # Game is scheduled
                if date_str:
                    try:
                        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        local_dt = dt.astimezone()
                        time_str = local_dt.strftime("%m/%d %I:%M %p")
                        formatted = f"{our_team_name} vs {other_team_name} ({time_str})"
                    except:
                        formatted = f"{our_team_name} vs {other_team_name} (TBD)"
                        timestamp = 9999999999  # Put TBD games last
                else:
                    formatted = f"{our_team_name} vs {other_team_name} (TBD)"
                    timestamp = 9999999999  # Put TBD games last
                    
            elif status_name == 'STATUS_HALFTIME':
                # Game is at halftime
                formatted = f"{our_team_name} {our_score}-{other_score} {other_team_name} (HT)"
                timestamp = -2  # Halftime games second priority after live games
            elif status_name == 'STATUS_FULL_TIME':
                # Soccer game is finished - put these last
                formatted = f"{our_team_name} {our_score}-{other_score} {other_team_name} (FT)"
                timestamp = 9999999998  # Final games second to last
            elif status_name == 'STATUS_FINAL':
                # Other sports game is finished - put these last
                formatted = f"{our_team_name} {our_score}-{other_score} {other_team_name} (F)"
                timestamp = 9999999998  # Final games second to last
                
            else:
                # Other status
                formatted = f"{our_team_name} {our_score}-{other_score} {other_team_name} ({status_name})"
                timestamp = 9999999997  # Other statuses third to last
            
            return {
                'timestamp': timestamp,
                'formatted': formatted,
                'sport': sport,
                'status': status_name
            }
                
        except Exception as e:
            self.logger.error(f"Error parsing game event with timestamp: {e}")
            return None

    def parse_game_event(self, event: Dict, team_id: str) -> Optional[str]:
        """Parse a game event and return formatted score info"""
        try:
            competitions = event.get('competitions', [])
            if not competitions:
                return None
            
            competition = competitions[0]
            competitors = competition.get('competitors', [])
            
            if len(competitors) != 2:
                return None
            
            # Check if our team is in this game
            our_team = None
            other_team = None
            
            for competitor in competitors:
                if competitor.get('team', {}).get('id') == team_id:
                    our_team = competitor
                else:
                    other_team = competitor
            
            if not our_team or not other_team:
                return None
            
            # Extract team info
            our_team_name = our_team.get('team', {}).get('abbreviation', 'UNK')
            other_team_name = other_team.get('team', {}).get('abbreviation', 'UNK')
            
            # Get scores
            our_score = our_team.get('score', '0')
            other_score = other_team.get('score', '0')
            
            # Get game status
            status = event.get('status', {})
            status_type = status.get('type', {})
            status_name = status_type.get('name', 'UNKNOWN')
            
            # Format based on game status
            if status_name in ['STATUS_IN_PROGRESS', 'STATUS_FIRST_HALF', 'STATUS_SECOND_HALF']:
                # Game is live
                clock = status.get('displayClock', '')
                period = status.get('period', 0)
                
                # Format period based on sport (need to determine sport from team_info)
                # This is a legacy method, so we'll use a generic approach
                if period <= 2:
                    period_str = f"{period}H"  # Likely soccer (halves)
                elif period <= 4:
                    period_str = f"Q{period}"  # Likely football (quarters)
                else:
                    period_str = f"{period}I"  # Likely baseball (innings)
                
                return f"{our_team_name} {our_score}-{other_score} {other_team_name} ({clock} {period_str})"
            
            elif status_name == 'STATUS_SCHEDULED':
                # Game is scheduled
                date_str = event.get('date', '')
                if date_str:
                    try:
                        # Parse date and format
                        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        # Convert to local time (assuming Pacific for Seattle teams)
                        local_dt = dt.astimezone()
                        time_str = local_dt.strftime("%m/%d %I:%M %p")
                        return f"{our_team_name} vs {other_team_name} ({time_str})"
                    except:
                        return f"{our_team_name} vs {other_team_name} (TBD)"
                else:
                    return f"{our_team_name} vs {other_team_name} (TBD)"
            
            elif status_name == 'STATUS_HALFTIME':
                # Game is at halftime
                return f"{our_team_name} {our_score}-{other_score} {other_team_name} (HT)"
            elif status_name == 'STATUS_FULL_TIME':
                # Soccer game is finished
                return f"{our_team_name} {our_score}-{other_score} {other_team_name} (FT)"
            elif status_name == 'STATUS_FINAL':
                # Other sports game is finished
                return f"{our_team_name} {our_score}-{other_score} {other_team_name} (F)"
            
            else:
                # Other status
                return f"{our_team_name} {our_score}-{other_score} {other_team_name} ({status_name})"
                
        except Exception as e:
            self.logger.error(f"Error parsing game event: {e}")
            return None
