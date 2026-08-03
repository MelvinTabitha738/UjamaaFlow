from flask import Blueprint, render_template, request, redirect, flash, url_for, current_app
from flask_login import login_required, current_user
from .models import Donation
from .models import Request as ResourceRequest
from .models import Match, DonationMedia, DonationReport, User
from . import db
import os
from werkzeug.utils import secure_filename

main = Blueprint('main', __name__)

@main.route('/')
def home():
    total_donations = Donation.query.count()
    families_helped = Match.query.filter_by(status='matched').count() + ResourceRequest.query.filter_by(fulfilled=True).count()
    active_donors = db.session.query(db.func.count(db.func.distinct(Donation.donor_id))).scalar() or 0
    return render_template(
        'home.html',
        total_donations=total_donations,
        families_helped=families_helped,
        active_donors=active_donors
    )

@main.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'donor':
        donor_donations = Donation.query.filter_by(donor_id=current_user.id).order_by(Donation.id.desc()).all()
        total_donations = len(donor_donations)
        matched_donations = len([d for d in donor_donations if d.matched])
        unmatched_donations = total_donations - matched_donations
        lives_impacted = matched_donations
        success_rate = int((matched_donations / total_donations) * 100) if total_donations else 0
        recent_donations = donor_donations[:5]
        return render_template(
            'dashboard/donor_dashboard.html',
            total_donations=total_donations,
            matched_donations=matched_donations,
            unmatched_donations=unmatched_donations,
            lives_impacted=lives_impacted,
            success_rate=success_rate,
            recent_donations=recent_donations,
        )
    elif current_user.role == 'recipient':
        my_requests = ResourceRequest.query.filter_by(recipient_id=current_user.id).order_by(ResourceRequest.id.desc()).all()
        total_requests = len(my_requests)
        fulfilled_requests = len([r for r in my_requests if r.fulfilled])
        pending_requests = total_requests - fulfilled_requests
        available_donations = Donation.query.filter_by(matched=False).order_by(Donation.id.desc()).all()
        return render_template(
            'dashboard/recipient_dashboard.html',
            my_requests=my_requests,
            total_requests=total_requests,
            fulfilled_requests=fulfilled_requests,
            pending_requests=pending_requests,
            available_donations=available_donations,
            donations=available_donations
        )
    elif current_user.role == 'admin':
        return redirect(url_for('main.admin_dashboard'))
    else:
        return render_template('home.html')

@main.route('/donate', methods=['GET', 'POST'])
@login_required
def donate():
    if current_user.role != 'donor':
        flash("You are not a donor. Cannot donate.", "error")
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        # Support multi-item donations: items[] arrays
        items = request.form.getlist('item[]')
        categories = request.form.getlist('category[]')
        quantities = request.form.getlist('quantity[]')
        descriptions = request.form.getlist('description[]')
        locations = request.form.getlist('location[]')
        contact_methods = request.form.getlist('contact_method[]')
        phone_numbers = request.form.getlist('phone_number[]')
        images = request.files.getlist('donation_image[]')

        if not items or not any(i.strip() for i in items):
            flash("Please provide at least one item.", "error")
            return redirect(url_for('main.donate'))

        saved_count = 0
        for i, item in enumerate(items):
            item = item.strip()
            if not item:
                continue

            category = categories[i] if i < len(categories) else 'General'
            quantity = quantities[i] if i < len(quantities) else ''
            description = descriptions[i] if i < len(descriptions) else ''
            location = locations[i] if i < len(locations) else ''
            contact_method = contact_methods[i] if i < len(contact_methods) else 'email'
            phone_number = phone_numbers[i].strip() if i < len(phone_numbers) else ''

            # Validate Kenyan phone number if contact method is phone
            if contact_method == 'phone':
                import re
                ke_phone_re = re.compile(r'^(?:\+?254|0)[17]\d{8}$')
                if not phone_number or not ke_phone_re.match(phone_number.replace(' ', '')):
                    flash(f"Item {i+1}: Please enter a valid Kenyan phone number (e.g. 0712345678 or +254712345678).", "error")
                    return redirect(url_for('main.donate'))

            new_donation = Donation(
                donor_id=current_user.id,
                item=item,
                category=category or 'General',
                quantity=quantity,
                description=description,
                location=location
            )
            db.session.add(new_donation)
            db.session.flush()  # get the ID before commit

            # Handle image upload for this item
            image_file = images[i] if i < len(images) else None
            if image_file and image_file.filename:
                filename = secure_filename(image_file.filename)
                if not image_file.mimetype.startswith('image/'):
                    flash(f'Item {i+1}: Only image uploads are allowed.')
                    continue
                image_file.seek(0, os.SEEK_END)
                size_bytes = image_file.tell()
                image_file.seek(0)
                if size_bytes > 5 * 1024 * 1024:
                    flash(f'Item {i+1}: Image must be <= 5MB.')
                    continue

                upload_dir = os.path.join(current_app.root_path, 'static', 'uploads')
                os.makedirs(upload_dir, exist_ok=True)
                save_path = os.path.join(upload_dir, filename)
                image_file.save(save_path)

                media = DonationMedia(donation_id=new_donation.id, file_path=f"/static/uploads/{filename}")
                db.session.add(media)

            saved_count += 1

        db.session.commit()
        if saved_count == 1:
            flash("Donation submitted! Thank you for your generosity. 🎉", "success")
        else:
            flash(f"{saved_count} donations submitted! Thank you for your generosity. 🎉", "success")
        return redirect(url_for('main.dashboard'))

    return render_template('donor/donate.html')

@main.route('/request-resource', methods=['GET', 'POST'])
@login_required
def request_resource():
    if current_user.role != 'recipient':
        flash("Access denied.")
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        item_needed = request.form.get('item_needed')
        category = request.form.get('category', 'General')
        quantity = request.form.get('quantity')
        reason = request.form.get('reason')
        location = request.form.get('location')

        new_request = ResourceRequest(
            recipient_id=current_user.id,
            item_needed=item_needed,
            category=category,
            quantity=quantity,
            reason=reason,
            location=location
        )
        db.session.add(new_request)
        db.session.commit()
        flash("Resource request submitted successfully!")
        return redirect(url_for('main.dashboard'))
    
    return render_template('recipient/request_form.html')

@main.route('/admin/matches')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash("Admins only.")
        return redirect(url_for('main.dashboard'))

    unmatched_donations = Donation.query.filter_by(matched=False).order_by(Donation.id.desc()).all()
    unfulfilled_requests = ResourceRequest.query.filter_by(fulfilled=False).order_by(ResourceRequest.id.desc()).all()
    total_users = User.query.count()
    total_donations = Donation.query.count()
    total_requests = ResourceRequest.query.count()
    total_reports = DonationReport.query.count()
    pending_approvals = DonationReport.query.count() + Donation.query.filter_by(flagged=True).count()
    matches = Match.query.order_by(Match.id.desc()).all()

    return render_template(
        'admin/match_dashboard.html',
        donations=unmatched_donations,
        requests=unfulfilled_requests,
        total_users=total_users,
        total_donations=total_donations,
        total_requests=total_requests,
        total_reports=total_reports,
        pending_approvals=pending_approvals,
        matches=matches
    )

@main.route('/admin/match', methods=['POST'])
@login_required
def create_match():
    if current_user.role != 'admin':
        flash("Admins only.")
        return redirect(url_for('main.dashboard'))

    donation_id = request.form.get('donation_id')
    request_id = request.form.get('request_id')
    donation = Donation.query.get(donation_id)
    req = ResourceRequest.query.get(request_id)
    if not donation or not req:
        flash('Invalid donation or request selected.')
        return redirect(url_for('main.admin_dashboard'))

    match = Match(donation_id=donation.id, request_id=req.id, status='matched')
    donation.matched = True
    req.fulfilled = True
    db.session.add(match)
    db.session.commit()
    flash('Match created successfully!')
    return redirect(url_for('main.admin_dashboard'))

@main.route('/browse')
@login_required
def browse():
    if current_user.role != 'recipient':
        flash('Only recipients can browse available donations.')
        return redirect(url_for('main.dashboard'))

    query = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    location = request.args.get('location', '').strip()

    donations_query = Donation.query.filter_by(matched=False)
    if query:
        donations_query = donations_query.filter(
            (Donation.item.ilike(f"%{query}%")) | (Donation.description.ilike(f"%{query}%"))
        )
    if category and category.lower() != 'all':
        donations_query = donations_query.filter(Donation.category.ilike(f"%{category}%"))
    if location:
        donations_query = donations_query.filter(Donation.location.ilike(f"%{location}%"))

    donations = donations_query.order_by(Donation.id.desc()).all()
    return render_template('recipient/browse.html', donations=donations, q=query, category=category, location=location)

@main.route('/admin/donations')
@login_required
def admin_donations():
    if current_user.role != 'admin':
        flash('Admins only.')
        return redirect(url_for('main.dashboard'))
    items = Donation.query.order_by(Donation.id.desc()).all()
    return render_template('admin/donations.html', donations=items)

@main.route('/admin/requests')
@login_required
def admin_requests():
    if current_user.role != 'admin':
        flash('Admins only.')
        return redirect(url_for('main.dashboard'))
    items = ResourceRequest.query.order_by(ResourceRequest.id.desc()).all()
    return render_template('admin/requests.html', requests=items)

@main.route('/admin/reports')
@login_required
def admin_reports():
    if current_user.role != 'admin':
        flash('Admins only.')
        return redirect(url_for('main.dashboard'))
    reports = DonationReport.query.order_by(DonationReport.id.desc()).all()
    return render_template('admin/reports.html', reports=reports)

@main.route('/admin/users')
@login_required
def admin_users():
    if current_user.role != 'admin':
        flash('Admins only.')
        return redirect(url_for('main.dashboard'))
    users = User.query.order_by(User.id.desc()).all()
    return render_template('admin/users.html', users=users)

@main.route('/admin/donation/<int:donation_id>/toggle', methods=['POST'])
@login_required
def admin_toggle_donation(donation_id):
    if current_user.role != 'admin':
        flash('Admins only.')
        return redirect(url_for('main.dashboard'))
    d = Donation.query.get_or_404(donation_id)
    d.matched = not d.matched
    db.session.commit()
    flash('Donation status updated.')
    return redirect(request.referrer or url_for('main.admin_donations'))

@main.route('/admin/request/<int:request_id>/toggle', methods=['POST'])
@login_required
def admin_toggle_request(request_id):
    if current_user.role != 'admin':
        flash('Admins only.')
        return redirect(url_for('main.dashboard'))
    r = ResourceRequest.query.get_or_404(request_id)
    r.fulfilled = not r.fulfilled
    db.session.commit()
    flash('Request status updated.')
    return redirect(request.referrer or url_for('main.admin_requests'))

@main.route('/admin/report/<int:report_id>/resolve', methods=['POST'])
@login_required
def admin_resolve_report(report_id):
    if current_user.role != 'admin':
        flash('Admins only.')
        return redirect(url_for('main.dashboard'))
    rep = DonationReport.query.get_or_404(report_id)
    db.session.delete(rep)
    db.session.commit()
    flash('Report resolved.')
    return redirect(request.referrer or url_for('main.admin_reports'))

@main.route('/donation/<int:donation_id>/report', methods=['POST'])
@login_required
def report_donation(donation_id):
    reason = request.form.get('reason', '').strip()
    donation = Donation.query.get_or_404(donation_id)
    report = DonationReport(donation_id=donation.id, reporter_id=current_user.id, reason=reason)
    donation.flagged = True
    db.session.add(report)
    db.session.commit()
    flash('Thank you for your report. Our team will review this listing.')
    return redirect(url_for('main.browse'))

@main.route('/contact')
def contact():
    return render_template('contact/contact.html')

@main.route('/resource')
def resource():
    donations = Donation.query.order_by(Donation.id.desc()).all()
    return render_template('resources/resource.html', donations=donations)

@main.route('/recipient')
@login_required
def recipient_dashboard():
    return redirect(url_for('main.dashboard'))

@main.route('/donations')
@login_required
def my_donations():
    if current_user.role != 'donor':
        flash('Only donors can view their donations.')
        return redirect(url_for('main.dashboard'))
    donor_donations = Donation.query.filter_by(donor_id=current_user.id).order_by(Donation.id.desc()).all()
    return render_template('donor/my_donations.html', donations=donor_donations)