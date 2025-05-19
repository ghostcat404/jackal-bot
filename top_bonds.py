#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import urllib.request
import re
import time
import sys
import datetime

def get_top_yield_bonds(count=5):
    """
    Scrapes bond data from smart-lab.ru and returns the top bonds by yield to maturity.
    
    Args:
        count: Number of top bonds to return (default: 5)
        
    Returns:
        List of dictionaries containing the top bonds sorted by yield to maturity
    """
    try:
        # Print status message
        print("Fetching data from smart-lab.ru...")
        
        # URL for corporate bonds page on smart-lab.ru
        url = "https://smart-lab.ru/q/bonds/"
        
        # Add headers to mimic a browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        
        # Create a request object
        request = urllib.request.Request(url, headers=headers)
        
        # Make the API request
        response = urllib.request.urlopen(request)
        
        # Read the HTML content
        html_content = response.read().decode('utf-8')
        
        # Find all tables on the page
        table_pattern = r'<table[^>]*>(.*?)</table>'
        tables = re.findall(table_pattern, html_content, re.DOTALL)
        
        if not tables:
            print("Could not find any tables on the page.")
            return None
        
        # Look for a table that contains the headers we're interested in
        table_content = None
        for table in tables:
            # Check if this table contains the headers we're looking for
            if 'Доходн' in table and 'Рейтинг' in table:
                table_content = table
                break
        
        if not table_content:
            print("Could not find the bonds table on the page.")
            return None
        
        # Extract table headers
        header_pattern = r'<tr[^>]*>(.*?)</tr>'
        header_match = re.search(header_pattern, table_content, re.DOTALL)
        
        if not header_match:
            print("Could not find the table headers.")
            return None
        
        header_row = header_match.group(1)
        header_pattern = r'<th[^>]*>(.*?)</th>'
        headers = re.findall(header_pattern, header_row, re.DOTALL)
        headers = [h.strip() for h in headers]
        
        # Find the index of relevant columns
        # Column indices may vary, so we'll search for them by name
        # We need to handle HTML tags and line breaks in the headers
        name_idx = next((i for i, h in enumerate(headers) if 'Имя' in h), None)
        ytm_idx = next((i for i, h in enumerate(headers) if 'Доходн' in h), None)
        rating_idx = next((i for i, h in enumerate(headers) if 'Рейтинг' in h), None)
        
        # For maturity, we need to handle the line break in "Лет до<br/>погаш."
        maturity_idx = next((i for i, h in enumerate(headers) if 'Лет до' in h), None)
        
        # Find the offer date column
        offer_date_idx = next((i for i, h in enumerate(headers) if 'Оферта' in h), None)
        
        # Debug: print all headers
        print("Found headers: {}".format(headers))
        print("Column indices - Name: {}, Yield: {}, Rating: {}, Maturity: {}, Offer Date: {}".format(
            name_idx, ytm_idx, rating_idx, maturity_idx, offer_date_idx
        ))
        
        # Check if we found all required columns
        if None in [ytm_idx]:
            print("Could not find all required columns in the table.")
            print("Available columns: {}".format(headers))
            return None
        
        # Extract bond data
        bonds_list = []
        
        # Find all rows in the table (skip the header row)
        row_pattern = r'<tr[^>]*>(.*?)</tr>'
        rows = re.findall(row_pattern, table_content, re.DOTALL)
        
        # Skip the header row
        for row in rows[1:]:
            # Extract cells from the row
            cell_pattern = r'<td[^>]*>(.*?)</td>'
            cells = re.findall(cell_pattern, row, re.DOTALL)
            
            # Skip rows with insufficient cells
            if len(cells) <= max(filter(None, [name_idx, ytm_idx, rating_idx, maturity_idx])):
                continue
            
            # Extract data from cells
            name_html = cells[name_idx].strip() if name_idx is not None and name_idx < len(cells) else ""
            
            # Extract the bond name and ISIN from the HTML
            name_match = re.search(r'title="[^"]*\s+\(([^)]+)\)"[^>]*>([^<]+)</a>', name_html)
            if name_match:
                isin = name_match.group(1)
                name = name_match.group(2)
            else:
                # If we can't extract the ISIN and name from the link, just strip HTML tags
                isin = "N/A"
                name = re.sub(r'<[^>]+>', '', name_html).strip()
            
            # Extract yield to maturity and convert to float
            ytm_text = cells[ytm_idx].strip() if ytm_idx is not None and ytm_idx < len(cells) else "0"
            ytm_text = ytm_text.replace('%', '').replace(',', '.').strip()
            try:
                ytm = float(ytm_text)
            except ValueError:
                ytm = 0.0
            
            # Extract rating
            rating = cells[rating_idx].strip() if rating_idx is not None and rating_idx < len(cells) else "N/A"
            
            # Extract maturity (years to maturity)
            maturity_text = cells[maturity_idx].strip() if maturity_idx is not None and maturity_idx < len(cells) else ""
            try:
                maturity = float(maturity_text.replace(',', '.'))
                maturity_str = "{:.1f} years".format(maturity)
            except (ValueError, AttributeError):
                maturity = 0.0
                maturity_str = "N/A"
            
            # Extract offer date and calculate years to offer if available
            offer_date = "N/A"
            years_to_offer = None
            if offer_date_idx is not None and offer_date_idx < len(cells):
                offer_date = cells[offer_date_idx].strip()
                # Remove any HTML tags
                offer_date = re.sub(r'<[^>]+>', '', offer_date).strip()
                
                # If offer date is available, calculate years to offer
                if offer_date and offer_date != "N/A" and offer_date != "-":
                    print(f"Processing offer date: '{offer_date}' for bond {name}")
                    try:
                        # Parse the date (assuming format is DD.MM.YYYY)
                        day, month, year = map(int, offer_date.split('.'))
                        
                        # Handle 2-digit year (assuming 20xx)
                        if year < 100:
                            year += 2000
                            
                        offer_date_obj = datetime.date(year, month, day)
                        
                        # Calculate years to offer
                        today = datetime.date.today()
                        days_to_offer = (offer_date_obj - today).days
                        
                        if days_to_offer > 0:
                            years_to_offer = days_to_offer / 365.0
                            print(f"  Calculated years to offer: {years_to_offer:.2f} years")
                        else:
                            # If offer date is in the past, set to N/A
                            offer_date = "N/A"
                            print(f"  Offer date is in the past, setting to N/A")
                    except (ValueError, AttributeError, IndexError) as e:
                        # If date parsing fails, keep the original date string
                        print(f"  Error parsing offer date: {e}")
                elif offer_date == "-":
                    # If offer date is "-", set to N/A
                    offer_date = "N/A"
                
                # If empty, set to N/A
                if not offer_date:
                    offer_date = "N/A"
            
            # Check if this is a fixed-income bond
            # For now, we'll assume all bonds in the table are fixed-income
            
            bond = {
                'ISIN': isin,
                'Name': name,
                'Yield to Maturity': ytm,
                'Rating': rating,
                'Maturity': maturity_str,
                'Offer Date': offer_date
            }
            
            # Add years to offer if available
            if years_to_offer is not None:
                bond['Years to Offer'] = years_to_offer
                # Format years to offer as a string (similar to maturity)
                bond['Years to Offer Str'] = "{:.1f} years".format(years_to_offer)
            
            bonds_list.append(bond)
        
        # Sort bonds by Yield to Maturity in descending order
        sorted_bonds = sorted(bonds_list, key=lambda x: x['Yield to Maturity'], reverse=True)
        
        # Return the top N bonds by yield
        return sorted_bonds[:count]
        
    except urllib.error.URLError as e:
        print("Error fetching data: {}".format(e))
        return None
    except Exception as e:
        print("An error occurred: {}".format(e))
        return None

def print_table(data):
    """
    Prints data in a formatted table.
    
    Args:
        data: List of dictionaries containing the bond data
    """
    if not data:
        print("No data to display.")
        return
    
    # Define the columns to display
    columns = ['ISIN', 'Name', 'Yield to Maturity', 'Rating', 'Maturity', 'Offer Date', 'Years to Offer Str']
    
    # Calculate column widths
    widths = {col: len(col) for col in columns}
    for item in data:
        for col in columns:
            if col in item:
                # Convert value to string
                value = item[col]
                if col == 'Yield to Maturity':
                    value = "{:.2f}%".format(value) if value is not None else "N/A"
                value_str = str(value) if value is not None else "N/A"
                widths[col] = max(widths[col], len(value_str))
    
    # Print header
    header_line = " | ".join(col.ljust(widths[col]) for col in columns)
    print(header_line)
    print("-" * len(header_line))
    
    # Print data rows
    for item in data:
        row_values = []
        for col in columns:
            value = item.get(col, "N/A")
            if col == 'Yield to Maturity':
                value = "{:.2f}%".format(value) if value is not None else "N/A"
            value_str = str(value) if value is not None else "N/A"
            row_values.append(value_str.ljust(widths[col]))
        print(" | ".join(row_values))

def main():
    """Main function to run the script."""
    try:
        # Get the top 10 bonds by yield to maturity
        top_bonds = get_top_yield_bonds(10)
        
        if top_bonds and len(top_bonds) > 0:
            print("\nTop 10 bonds with highest yield to maturity:")
            print("=" * 80)
            
            # Print the data as a table
            print_table(top_bonds)
            print("\nData from smart-lab.ru")
        else:
            print("Failed to retrieve bond data.")
            
    except Exception as e:
        print("An error occurred while running the program: {}".format(e))

if __name__ == "__main__":
    main()
