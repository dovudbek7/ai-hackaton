import json
import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from hackathon.models import Region, School

def import_data(json_file):
    # Clear existing data
    print("Clearing existing Region and School data...")
    Region.objects.all().delete()
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Dictionary to keep track of created regions
    regions_cache = {}
    
    # Counter for created objects
    regions_count = 0
    schools_count = 0

    for entry in data:
        tuman_name = entry.get('Туман')
        maktab_name = entry.get('Мактаб')
        
        # Skip entries that are clearly summary or total rows
        # Based on the sample: {"№": "Андижон вилояти жами", "Туман": null, "Мактаб": 764}
        if tuman_name is None:
            continue
            
        # Skip if Maktab is a number (it means it's a subtotal for that district)
        if isinstance(maktab_name, int):
            continue

        # Get or create the Region
        if tuman_name not in regions_cache:
            region, created = Region.objects.get_or_create(name=tuman_name)
            regions_cache[tuman_name] = region
            if created:
                regions_count += 1
                
        region = regions_cache[tuman_name]
        
        # Create the School
        _, created = School.objects.get_or_create(
            region=region,
            name=maktab_name
        )
        if created:
            schools_count += 1

    print(f"Import complete!")
    print(f"Created {regions_count} new regions.")
    print(f"Created {schools_count} new schools.")

if __name__ == "__main__":
    import_data('maktab_soni.json')
