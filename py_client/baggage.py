import urllib.parse

ROUTING_KEY = "sd-routing-key"

class Baggage:    

    def extract_routing_key_from_baggage(self, baggage_header_value: str) -> str :

        if not baggage_header_value:
            return None
        
        # Split the baggage string by comma for multiple entries
        entries = baggage_header_value.split(',')
        
        for entry in entries:
            # Each entry might have properties separated by semicolon,
            # we are interested in the main key-value pair.
            key_value_part = entry.split(';', 1)[0].strip()
            
            if '=' in key_value_part:
                key, value = key_value_part.split('=', 1)
                key = key.strip()
                # Values might be URL-encoded, though typically not for simple identifiers.
                # The spec mentions URL decoding for values.
                # For simplicity here, we'll assume sd-routing-key values don't need complex decoding
                # beyond what strip() handles for spaces. If they can be URL encoded, use:
                # value = urllib.parse.unquote(value.strip())
                value = value.strip()
                
                if key == ROUTING_KEY:
                    return value
                    
        return None