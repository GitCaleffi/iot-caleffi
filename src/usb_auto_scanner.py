import csv
import datetime

# Path to output CSV file
output_file = "barcodes.csv"

# Open CSV file in append mode
with open(output_file, "a", newline="") as csvfile:
    writer = csv.writer(csvfile)
    print("Ready to scan barcodes. Press Ctrl+C to exit.")

    try:
        while True:
            # Wait for barcode input from USB scanner
            barcode = input()  # USB scanner acts like a keyboard
            barcode = barcode.strip()

            if barcode:  # ignore empty scans
                timestamp = datetime.datetime.now()
                print(f"Scanned: {barcode} at {timestamp}")
                writer.writerow([timestamp, barcode])
                csvfile.flush()

    except KeyboardInterrupt:
        print("\nExiting... CSV saved.")
