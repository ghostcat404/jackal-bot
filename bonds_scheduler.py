#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import datetime
import sys
import top_bonds

def get_bonds_data():
    """Get top bonds data and format it as a text report."""
    print("Fetching data from smart-lab.ru...")
    
    try:
        # Get the top 10 bonds
        bonds = top_bonds.get_top_yield_bonds(10)
        
        if bonds and len(bonds) > 0:
            # Format the bonds data as a table
            report = "Топ-10 облигаций с наибольшей доходностью к погашению:\n"
            report += "=" * 80 + "\n"
            
            # Define the columns to display
            columns = ['ISIN', 'Name', 'Yield to Maturity', 'Rating', 'Maturity']
            
            # Calculate column widths
            widths = {col: len(col) for col in columns}
            for item in bonds:
                for col in columns:
                    if col in item:
                        # Convert value to string
                        value = item[col]
                        if col == 'Yield to Maturity':
                            value = "{:.2f}%".format(value) if value is not None else "N/A"
                        value_str = str(value) if value is not None else "N/A"
                        widths[col] = max(widths[col], len(value_str))
            
            # Add header
            header_line = " | ".join(col.ljust(widths[col]) for col in columns)
            report += header_line + "\n"
            report += "-" * len(header_line) + "\n"
            
            # Add data rows
            for item in bonds:
                row_values = []
                for col in columns:
                    value = item.get(col, "N/A")
                    if col == 'Yield to Maturity':
                        value = "{:.2f}%".format(value) if value is not None else "N/A"
                    value_str = str(value) if value is not None else "N/A"
                    row_values.append(value_str.ljust(widths[col]))
                report += " | ".join(row_values) + "\n"
            
            report += "\nДанные с сайта smart-lab.ru"
            report += "\nОтчет сгенерирован: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            return report
        else:
            return "Не удалось получить данные по облигациям."
        
    except Exception as e:
        print("Error fetching bonds data: {}".format(e))
        return "Произошла ошибка при получении данных: {}".format(e)

def save_report_to_file(report, filename="bonds_report.txt"):
    """Save the report to a file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(report)
        print("Report saved to {}".format(filename))
        return True
    except Exception as e:
        print("Error saving report: {}".format(e))
        return False

def run_scheduled_report(interval_hours=24):
    """Run the report generation on a schedule."""
    print("Starting scheduled bond reports...")
    print("Reports will be generated every {} hours.".format(interval_hours))
    print("Press Ctrl+C to stop.")
    
    try:
        while True:
            # Generate and save the report
            report = get_bonds_data()
            save_report_to_file(report)
            
            # Wait for the next interval
            print("Next report will be generated in {} hours.".format(interval_hours))
            time.sleep(interval_hours * 3600)
    except KeyboardInterrupt:
        print("Scheduled reports stopped.")

def main():
    """Main function."""
    # Generate a report immediately
    report = get_bonds_data()
    print("\n" + report + "\n")
    
    # Ask if the user wants to save the report
    save = input("Save this report to a file? (y/n): ").lower()
    if save == 'y':
        filename = input("Enter filename (default: bonds_report.txt): ").strip()
        if not filename:
            filename = "bonds_report.txt"
        save_report_to_file(report, filename)
    
    # Ask if the user wants to schedule regular reports
    schedule = input("Schedule regular reports? (y/n): ").lower()
    if schedule == 'y':
        interval = input("Enter interval in hours (default: 24): ").strip()
        try:
            interval_hours = int(interval) if interval else 24
            run_scheduled_report(interval_hours)
        except ValueError:
            print("Invalid interval. Using default (24 hours).")
            run_scheduled_report(24)

if __name__ == "__main__":
    main()
