# blueprints/csv.py
# CSV import, export, and template-download routes.
from flask import (
    render_template, request, send_file, redirect, url_for, flash, abort,
    current_app
)
from flask_login import login_required, current_user
from extensions import db
from utils import (
    process_inventory_row, process_movement_row,
    process_disposed_item_row, generate_inventory_csv, generate_movements_csv,
    generate_disposals_csv, generate_inventory_template, generate_movements_template,
    generate_disposals_template
)
from datetime import datetime, timezone
from io import StringIO, BytesIO
import csv
import zipfile

from flask import Blueprint

# NOTE: The Blueprint variable is named `csv_bp` (not `csv`) to avoid
# shadowing the standard-library `csv` module imported above, which is
# used by this module's import handler.
csv_bp = Blueprint('csv', __name__)


@csv_bp.route('/import_csv', methods=['POST'])
@login_required
def import_csv():
    """Handles CSV imports for different inventory contexts."""
    context = request.form.get('context', '').lower()
    if context not in ['current_inventory', 'movement_tracker', 'disposed_items']:
        flash('Invalid import context specified', 'danger')
        return redirect(request.referrer)

    if 'csv_file' not in request.files or not request.files['csv_file'].filename:
        flash('No file uploaded', 'warning')
        return redirect(request.referrer)

    file = request.files['csv_file']
    try:
        stream = StringIO(file.read().decode('utf-8-sig'))
        csv_reader = csv.DictReader(stream)
        for row in csv_reader:
            if context == 'current_inventory':
                process_inventory_row(row)
            elif context == 'movement_tracker':
                process_movement_row(row)
            elif context == 'disposed_items':
                process_disposed_item_row(row, current_user)
        db.session.commit()
        flash('CSV imported successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Import failed: {str(e)}', 'danger')
        current_app.logger.error(f'CSV Import Failure: {str(e)}', exc_info=True)
    return redirect(url_for('inventory.index'))


@csv_bp.route('/export_csv')
@login_required
def export_csv():
    """Handles both single CSV and combined ZIP exports."""
    export_type = request.args.get('type', 'inventory')
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    if export_type == 'all':
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr(f'inventory_{timestamp}.csv', generate_inventory_csv())
            zip_file.writestr(f'movements_{timestamp}.csv', generate_movements_csv())
            zip_file.writestr(f'disposals_{timestamp}.csv', generate_disposals_csv())
        buffer.seek(0)
        return send_file(buffer, download_name=f'export_all_{timestamp}.zip', as_attachment=True, mimetype='application/zip')

    data = {
        'inventory': generate_inventory_csv,
        'movements': generate_movements_csv,
        'disposals': generate_disposals_csv
    }.get(export_type, lambda: abort(400))()
    buffer = BytesIO()
    buffer.write(data.encode('utf-8-sig'))
    buffer.seek(0)
    return send_file(buffer, download_name=f'{export_type}_{timestamp}.csv', as_attachment=True, mimetype='text/csv')


@csv_bp.route('/download_template')
@login_required
def download_template():
    template_type = request.args.get('type', 'inventory')
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    if template_type == 'all':
        # Create ZIP with all templates
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            inv_data = generate_inventory_template()
            zip_file.writestr(f'inventory_template_{timestamp}.csv', inv_data)
            mov_data = generate_movements_template()
            zip_file.writestr(f'movements_template_{timestamp}.csv', mov_data)
            dis_data = generate_disposals_template()
            zip_file.writestr(f'disposals_template_{timestamp}.csv', dis_data)
        buffer.seek(0)
        return send_file(
            buffer,
            download_name=f'all_templates_{timestamp}.zip',
            as_attachment=True,
            mimetype='application/zip'
        )
    elif template_type == 'inventory':
        data = generate_inventory_template()
        filename = f'inventory_template_{timestamp}.csv'
    elif template_type == 'movements':
        data = generate_movements_template()
        filename = f'movements_template_{timestamp}.csv'
    elif template_type == 'disposals':
        data = generate_disposals_template()
        filename = f'disposals_template_{timestamp}.csv'
    else:
        abort(400, "Invalid template type")

    buffer = BytesIO()
    buffer.write(data.encode('utf-8-sig'))
    buffer.seek(0)
    return send_file(
        buffer,
        download_name=filename,
        as_attachment=True,
        mimetype='text/csv'
    )