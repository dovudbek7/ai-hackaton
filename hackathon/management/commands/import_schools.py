import json
from django.core.management.base import BaseCommand
from hackathon.models import Region, School


class Command(BaseCommand):
    help = 'Import regions and schools from schools.json file'

    def add_arguments(self, parser):
        parser.add_argument(
            'json_file',
            type=str,
            help='Path to the schools.json file'
        )

    def handle(self, *args, **options):
        json_file = options['json_file']
        
        self.stdout.write(self.style.WARNING(f'Reading data from {json_file}...'))
        
        # Read JSON file
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'File not found: {json_file}'))
            return
        except json.JSONDecodeError:
            self.stdout.write(self.style.ERROR(f'Invalid JSON file: {json_file}'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'Loaded {len(data)} records'))
        
        # Track statistics
        regions_created = 0
        schools_created = 0
        schools_skipped = 0
        
        # Process each record
        for record in data:
            tuman = record.get('tuman', '').strip()
            maktab = record.get('maktab', '').strip()
            
            if not tuman or not maktab:
                continue
            
            # Get or create region (tuman)
            region, created = Region.objects.get_or_create(
                name=tuman,
                defaults={'is_open': True}
            )
            
            if created:
                regions_created += 1
                self.stdout.write(self.style.SUCCESS(f'  Created region: {tuman}'))
            
            # Check if school already exists for this region
            school_exists = School.objects.filter(
                region=region,
                name=maktab
            ).exists()
            
            if not school_exists:
                School.objects.create(
                    region=region,
                    name=maktab
                )
                schools_created += 1
            else:
                schools_skipped += 1
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n' + '='*50))
        self.stdout.write(self.style.SUCCESS('Import Summary:'))
        self.stdout.write(self.style.SUCCESS(f'  Regions created: {regions_created}'))
        self.stdout.write(self.style.SUCCESS(f'  Schools created: {schools_created}'))
        if schools_skipped > 0:
            self.stdout.write(self.style.WARNING(f'  Schools skipped (already exist): {schools_skipped}'))
        self.stdout.write(self.style.SUCCESS('='*50))
        self.stdout.write(self.style.SUCCESS('\nImport completed successfully!'))
