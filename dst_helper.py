# dst_helper.py
# Simple Daylight Saving Time helper for common regions

def is_dst_active(month, day, timezone_name="AUTO"):
    """
    Check if DST is active for common regions
    Returns: (is_dst, dst_offset_hours)
    """
    
    # DST periods for major regions (approximate)
    dst_rules = {
        "EU": {  # European Union (last Sunday in March to last Sunday in October)
            "start_month": 3, "start_day": 25,  # Approximate last Sunday
            "end_month": 10, "end_day": 25,     # Approximate last Sunday
            "offset": 1
        },
        "US": {  # United States (second Sunday in March to first Sunday in November)
            "start_month": 3, "start_day": 8,   # Approximate second Sunday
            "end_month": 11, "end_day": 1,      # Approximate first Sunday
            "offset": 1
        },
        "AU": {  # Australia (first Sunday in October to first Sunday in April)
            "start_month": 10, "start_day": 1,  # Approximate first Sunday
            "end_month": 4, "end_day": 1,       # Approximate first Sunday (next year)
            "offset": 1
        },
        "SA": {  # South America (Brazil, Paraguay, Chile - October to February/March)
            "start_month": 10, "start_day": 1,  # October start
            "end_month": 2, "end_day": 28,      # February end
            "offset": 1
        },
        "ME": {  # Middle East (Iran, Jordan, Lebanon, Syria - March to October)
            "start_month": 3, "start_day": 21,  # March equinox
            "end_month": 10, "end_day": 21,     # October
            "offset": 1
        },
        "AFRICA": {  # North Africa (Morocco - last Sunday in March to last Sunday in October)
            "start_month": 3, "start_day": 25,  # Approximate last Sunday
            "end_month": 10, "end_day": 25,     # Approximate last Sunday
            "offset": 1
        }
    }
    
    # Auto-detect based on common timezone patterns
    if timezone_name == "AUTO":
        # This is a simple heuristic - could be improved
        # For now, assume EU rules for most of Europe
        timezone_name = "EU"
    
    if timezone_name not in dst_rules:
        return False, 0
    
    rule = dst_rules[timezone_name]
    
    # Simple check - this is approximate and doesn't account for exact Sunday calculations
    if rule["start_month"] <= rule["end_month"]:
        # Northern hemisphere (March-October)
        is_dst = (month > rule["start_month"] or 
                 (month == rule["start_month"] and day >= rule["start_day"])) and \
                (month < rule["end_month"] or 
                 (month == rule["end_month"] and day <= rule["end_day"]))
    else:
        # Southern hemisphere (October-April)
        is_dst = (month >= rule["start_month"] or 
                 month <= rule["end_month"] or
                 (month == rule["start_month"] and day >= rule["start_day"]) or
                 (month == rule["end_month"] and day <= rule["end_day"]))
    
    return is_dst, rule["offset"] if is_dst else 0

def get_timezone_with_dst(base_offset, month, day, region="EU"):
    """
    Get timezone offset including DST
    
    Args:
        base_offset: Base timezone offset (e.g., 0 for GMT, 1 for CET)
        month: Current month (1-12)
        day: Current day (1-31)
        region: DST region ("EU", "US", "AU", or "NONE")
    
    Returns:
        Total timezone offset including DST
    """
    if region == "NONE":
        return base_offset
    
    is_dst, dst_offset = is_dst_active(month, day, region)
    return base_offset + dst_offset

# City-based timezone presets (like Windows Time Zone selector)
CITY_TIMEZONES = {
    # UTC/GMT
    "UTC+0: Coordinated Universal Time": {"offset": 0, "dst": "NONE"},
    "UTC+0: London, Dublin": {"offset": 0, "dst": "EU"},
    "UTC+0: Lisbon, Casablanca": {"offset": 0, "dst": "AFRICA"},
    
    # Europe
    "UTC+1: Paris, Berlin, Rome, Stockholm": {"offset": 1, "dst": "EU"},
    "UTC+1: Amsterdam, Brussels, Copenhagen": {"offset": 1, "dst": "EU"},
    "UTC+1: Prague, Vienna, Warsaw": {"offset": 1, "dst": "EU"},
    "UTC+2: Athens, Helsinki, Istanbul": {"offset": 2, "dst": "EU"},
    "UTC+2: Bucharest, Sofia, Tallinn": {"offset": 2, "dst": "EU"},
    "UTC+3: Moscow, St. Petersburg": {"offset": 3, "dst": "NONE"},
    
    # North America
    "UTC-5: New York, Toronto, Montreal": {"offset": -5, "dst": "US"},
    "UTC-5: Miami, Atlanta, Boston": {"offset": -5, "dst": "US"},
    "UTC-6: Chicago, Dallas, Mexico City": {"offset": -6, "dst": "US"},
    "UTC-7: Denver, Phoenix, Salt Lake City": {"offset": -7, "dst": "US"},
    "UTC-8: Los Angeles, San Francisco, Seattle": {"offset": -8, "dst": "US"},
    "UTC-9: Anchorage": {"offset": -9, "dst": "US"},
    "UTC-10: Honolulu": {"offset": -10, "dst": "NONE"},
    
    # Asia
    "UTC+9: Tokyo, Seoul, Osaka": {"offset": 9, "dst": "NONE"},
    "UTC+8: Beijing, Shanghai, Hong Kong": {"offset": 8, "dst": "NONE"},
    "UTC+8: Singapore, Kuala Lumpur": {"offset": 8, "dst": "NONE"},
    "UTC+7: Bangkok, Jakarta, Hanoi": {"offset": 7, "dst": "NONE"},
    "UTC+5.5: Mumbai, New Delhi, Kolkata": {"offset": 5.5, "dst": "NONE"},
    "UTC+4: Dubai, Abu Dhabi": {"offset": 4, "dst": "NONE"},
    "UTC+3.5: Tehran": {"offset": 3.5, "dst": "ME"},
    
    # Australia & Pacific
    "UTC+10: Sydney, Melbourne, Brisbane": {"offset": 10, "dst": "AU"},
    "UTC+9.5: Adelaide": {"offset": 9.5, "dst": "AU"},
    "UTC+8: Perth": {"offset": 8, "dst": "NONE"},
    "UTC+12: Auckland": {"offset": 12, "dst": "AU"},
    
    # South America
    "UTC-3: Buenos Aires, São Paulo": {"offset": -3, "dst": "SA"},
    "UTC-4: Santiago": {"offset": -4, "dst": "SA"},
    "UTC-5: Lima, Bogotá": {"offset": -5, "dst": "NONE"},
    
    # Africa
    "UTC+2: Cairo, Johannesburg": {"offset": 2, "dst": "NONE"},
    "UTC+1: Lagos, Kinshasa": {"offset": 1, "dst": "NONE"},
    "UTC+3: Nairobi, Addis Ababa": {"offset": 3, "dst": "NONE"},
}

# Legacy presets for backward compatibility
TIMEZONE_PRESETS = {
    "GMT/UTC": {"base": 0, "region": "NONE"},
    "UK/Ireland (GMT/BST)": {"base": 0, "region": "EU"},
    "Central Europe (CET/CEST)": {"base": 1, "region": "EU"},
    "Eastern Europe (EET/EEST)": {"base": 2, "region": "EU"},
    "US Eastern (EST/EDT)": {"base": -5, "region": "US"},
    "US Central (CST/CDT)": {"base": -6, "region": "US"},
    "US Mountain (MST/MDT)": {"base": -7, "region": "US"},
    "US Pacific (PST/PDT)": {"base": -8, "region": "US"},
    "Australia East (AEST/AEDT)": {"base": 10, "region": "AU"},
}
