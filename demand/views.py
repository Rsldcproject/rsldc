import json
import logging
import traceback
from datetime import datetime, timedelta
import csv
import os

from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, authenticate, login
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.db.models import Sum, Count, Max, Q
from django.db.models.functions import TruncMonth # <-- नया इम्पोर्ट (MySQL फिक्स के लिए)
from django.contrib import messages
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from .models import Survey, JobDemand, ApprenticeshipOJT, AssociationConsultation, AssociationJobRole, AssociationApprenticeship, GovtConsultation
from django.db.models import Sum, F, Count, Value, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.utils.dateparse import parse_date

logger = logging.getLogger(__name__)


# ============ HOME PAGE ============
def home(request):
    """Home page with 3 navigation buttons."""
    return render(request, 'home.html')

# ============================================
# PUBLIC FORM VIEWS
# ============================================

def survey_form(request):
    return render(request, 'form.html')


@csrf_exempt
@require_http_methods(["POST"])
def submit_survey(request):
    print("="*60)
    print("🔵 SUBMIT SURVEY API CALLED")
    print("="*60)
    
    try:
        # Check if request is multipart form data or JSON
        if request.content_type and 'multipart/form-data' in request.content_type:
            data = request.POST.dict()
            files = request.FILES
            
            # Convert string values that might be JSON
            if 'workforce_profile' in data and isinstance(data['workforce_profile'], str):
                try:
                    data['workforce_profile'] = json.loads(data['workforce_profile'])
                except:
                    pass
            
            if 'job_demands' in data:
                try:
                    data['job_demands'] = json.loads(data['job_demands'])
                except:
                    data['job_demands'] = []
            
            if 'apprenticeships' in data:
                try:
                    data['apprenticeships'] = json.loads(data['apprenticeships'])
                except:
                    data['apprenticeships'] = []
        else:
            data = json.loads(request.body)
            files = {}
        
        print(f"✅ Data Parsed Successfully")
        
        with transaction.atomic():
            survey = Survey.objects.create(
                company_code=data.get('company_code', '').strip(),
                start_time=data.get('start_time', ''),
                completion_time=data.get('completion_time', ''),
                submission_date=data.get('submission_date') or datetime.now().date(),
                field_officer_name=data.get('field_officer_name', '').strip(),
                company_name=data.get('company_name', '').strip(),
                organisation_type=data.get('organisation_type', '').strip(),
                organisation_type_other=data.get('organisation_type_other', '').strip(),
                product_service=data.get('product_service', '').strip(),
                product_service_specify=data.get('product_service_specify', '').strip(),
                operational_sector=data.get('operational_sector', '').strip(),
                operational_sector_other=data.get('operational_sector_other', '').strip(),
                company_size=data.get('company_size', '').strip(),
                address=data.get('address', '').strip(),
                website=data.get('website', '').strip(),
                district=data.get('district', '').strip(),
                block=data.get('block', '').strip(),
                contact_name=data.get('contact_name', '').strip(),
                contact_mobile=data.get('contact_mobile', '').strip(),
                contact_email=data.get('contact_email', '').strip(),
                has_hr=data.get('has_hr', 'No'),
                workforce_profile=data.get('workforce_profile', ''), # Fixed: removed .strip()
                placement_willingness=data.get('placement_willingness', 'No'),
                apprenticeship_willingness=data.get('apprenticeship_willingness', 'No'),
                guest_lecture_interest=data.get('guest_lecture_interest', 'No'),
                industrial_visit_interest=data.get('industrial_visit_interest', 'No'),
                csr_interest=data.get('csr_interest', 'No'),
                ojt_internship_willingness=data.get('ojt_internship_willingness', 'No'),
                recruitment_challenges=data.get('recruitment_challenges', '').strip(),
                additional_remarks=data.get('additional_remarks', '').strip(),
                supporting_evidence=data.get('supporting_evidence', '').strip(),
            )
            
            # Handle file upload
            if 'supporting_document' in files:
                uploaded_file = files['supporting_document']
                if uploaded_file.size > 50 * 1024:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'File size exceeds 50KB limit.'
                    }, status=400)
                
                file_name = f"survey_{survey.id}_{uploaded_file.name}"
                saved_path = default_storage.save(
                    os.path.join('supporting_documents', file_name),
                    ContentFile(uploaded_file.read())
                )
                survey.supporting_document = saved_path
                survey.save()
            
            print(f"✅ Survey Created! ID: {survey.id}")
            
            # Job Demands
            job_demands_data = data.get('job_demands', [])
            if isinstance(job_demands_data, str):
                job_demands_data = json.loads(job_demands_data)
            
            for idx, job_data in enumerate(job_demands_data, 1):
                JobDemand.objects.create(
                    survey=survey,
                    row_no=idx,
                    job_role=job_data.get('job_role', '').strip(),
                    sector=job_data.get('sector', '').strip(),
                    qualification=job_data.get('qualification', '').strip(),
                    qualification_other=job_data.get('qualification_other', '').strip(),
                    experience=job_data.get('experience', '').strip(),
                    certification=job_data.get('certification', 'No'),
                    certification_detail=job_data.get('certification_detail', '').strip(),
                    salary_offered=job_data.get('salary_offered', '').strip(),
                    current_openings=int(job_data.get('current_openings') or 0), # Fixed: int("") crash
                    openings_6_months=int(job_data.get('openings_6_months') or 0),
                    openings_12_months=int(job_data.get('openings_12_months') or 0),
                    apprentice_ojt=job_data.get('apprentice_ojt', 'No'),
                    apprentice_ojt_detail=job_data.get('apprentice_ojt_detail', '').strip(),
                    gender_suitability=job_data.get('gender_suitability', 'Any / No Preference'),
                    pwd=job_data.get('pwd', 'NA'),
                    career_progression=job_data.get('career_progression', 'No'),
                    career_progression_years=job_data.get('career_progression_years', '').strip(),
                    career_next_position=job_data.get('career_next_position', '').strip(),
                    career_next_salary=job_data.get('career_next_salary', '').strip(),
                    additional_remarks=job_data.get('additional_remarks', '').strip()
                )
                print(f"  ✅ Job Demand #{idx} Created!")
            
            # Apprenticeships
            apprenticeships_data = data.get('apprenticeships', [])
            if isinstance(apprenticeships_data, str):
                apprenticeships_data = json.loads(apprenticeships_data)
            
            for idx, app_data in enumerate(apprenticeships_data, 1):
                ApprenticeshipOJT.objects.create(
                    survey=survey,
                    row_no=idx,
                    job_role=app_data.get('job_role', '').strip(),
                    opportunity_type=app_data.get('opportunity_type', ''),
                    seats_capacity=int(app_data.get('seats_capacity') or 0),
                    duration_months=int(app_data.get('duration_months') or 0),
                    monthly_stipend=int(app_data.get('monthly_stipend') or 0),
                    expected_start_month=app_data.get('expected_start_month', ''),
                    minimum_qualification=app_data.get('minimum_qualification', '').strip(),
                    minimum_qualification_other=app_data.get('minimum_qualification_other', '').strip(),
                    conversion_to_employment=app_data.get('conversion_to_employment', 'No')
                )
                print(f"  ✅ Apprenticeship #{idx} Created!")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Survey submitted successfully',
            'survey_id': survey.id
        }, status=201)
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        traceback.print_exc()
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


# ============================================
# ADMIN PORTAL VIEWS
# ============================================

def admin_login(request):
    if request.user.is_authenticated:
        return redirect('survey:admin_dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('survey:admin_dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'portal/login.html')


@login_required
def admin_dashboard(request):
    district_filter = request.GET.get('district', '').strip()
    block_filter    = request.GET.get('block', '').strip()
    sector_filter   = request.GET.get('sector', '').strip()

    # Defaults — agar koi section fail ho jaye to dashboard nahi tootega
    context = {
        'total_surveys': 0, 'total_jobs': 0, 'total_current': 0, 'total_future': 0,
        'survey_count': 0, 'survey_current': 0, 'survey_future': 0,
        'association_count': 0, 'association_jobs': 0,
        'association_current': 0, 'association_future': 0,
        'govt_count': 0, 'govt_current': 0, 'govt_future': 0, 'govt_investment': 0,
        'latest_surveys': [], 'latest_associations': [], 'latest_govt': [],
        'district_stats_json': '[]', 'block_stats_json': '[]',
        'product_service_data_json': '[]', 'sector_data_json': '[]',
        'source_breakdown_json': '[]',
        'all_districts': [], 'all_blocks': [], 'all_sectors': [],
        'selected_district': district_filter,
        'selected_block': block_filter,
        'selected_sector': sector_filter,
    }

    # ============================================================
    # 1. SURVEY
    # ============================================================
    try:
        survey_qs = Survey.objects.all()
        job_qs = JobDemand.objects.all()

        if district_filter:
            survey_qs = survey_qs.filter(district=district_filter)
            job_qs = job_qs.filter(survey__district=district_filter)
        if block_filter:
            survey_qs = survey_qs.filter(block=block_filter)
            job_qs = job_qs.filter(survey__block=block_filter)
        if sector_filter:
            survey_qs = survey_qs.filter(operational_sector=sector_filter)
            job_qs = job_qs.filter(sector=sector_filter)

        survey_count = survey_qs.count()
        total_jobs   = job_qs.count()

        # ✅ FIXED: single Sum with F() + Coalesce (no Sum()+Sum())
        s_agg = job_qs.aggregate(
            cur=Coalesce(Sum('current_openings'), Value(0)),
            f6 =Coalesce(Sum('openings_6_months'), Value(0)),
            f12=Coalesce(Sum('openings_12_months'), Value(0)),
        )
        survey_current = s_agg['cur']
        survey_future  = s_agg['f6'] + s_agg['f12']

        # Latest 5 surveys — manual sum, properties pe bharosa nahi
        latest_surveys = []
        for s in survey_qs.prefetch_related('job_demands').order_by('-created_at')[:5]:
            total_demand = sum(
                (jd.current_openings or 0) + (jd.openings_6_months or 0) + (jd.openings_12_months or 0)
                for jd in s.job_demands.all()
            )
            latest_surveys.append({
                'id': s.id,
                'employer_name': s.company_name,
                'district': s.district,
                'primary_sector': s.operational_sector,
                'total_demand': total_demand,
                'created_at': s.created_at.strftime('%d %b %Y, %I:%M %p') if s.created_at else '',
            })

        # District stats (Survey) ✅ FIXED
        district_stats = []
        for d in survey_qs.values('district').annotate(
            count=Count('id'),
            demand=Coalesce(
                Sum(F('job_demands__current_openings')
                    + F('job_demands__openings_6_months')
                    + F('job_demands__openings_12_months')),
                Value(0)
            )
        ).order_by('-demand')[:10]:
            if d['district']:
                district_stats.append({
                    'district': d['district'],
                    'count': d['count'],
                    'total_demand': d['demand'] or 0,
                })

        # Block stats ✅ FIXED
        block_stats = []
        for b in survey_qs.values('block').annotate(
            count=Count('id'),
            demand=Coalesce(
                Sum(F('job_demands__current_openings')
                    + F('job_demands__openings_6_months')
                    + F('job_demands__openings_12_months')),
                Value(0)
            )
        ).order_by('-demand')[:10]:
            if b['block']:
                block_stats.append({
                    'block': b['block'],
                    'count': b['count'],
                    'total_demand': b['demand'] or 0,
                })

        # Product/service ✅ FIXED
        ps_data = []
        for ps in job_qs.values('survey__product_service').annotate(
            count=Count('id'),
            cur=Coalesce(Sum('current_openings'), Value(0)),
            fut=Coalesce(Sum(F('openings_6_months') + F('openings_12_months')), Value(0))
        ):
            if ps['survey__product_service']:
                ps_data.append({
                    'type': ps['survey__product_service'],
                    'count': ps['count'],
                    'total_current': ps['cur'] or 0,
                    'total_future': ps['fut'] or 0,
                })

        # Survey sector (raw, will merge later) ✅ FIXED
        survey_sector_raw = []
        for s in job_qs.values('sector').annotate(
            cur=Coalesce(Sum('current_openings'), Value(0)),
            fut=Coalesce(Sum(F('openings_6_months') + F('openings_12_months')), Value(0))
        ):
            if s['sector']:
                survey_sector_raw.append({
                    'sector': s['sector'],
                    'current': s['cur'] or 0,
                    'future': s['fut'] or 0,
                })

        all_districts = [x for x in Survey.objects.values_list('district', flat=True).distinct().order_by('district') if x]
        all_blocks    = [x for x in Survey.objects.values_list('block', flat=True).distinct().order_by('block') if x]
        all_sectors   = [x for x in JobDemand.objects.values_list('sector', flat=True).distinct().order_by('sector') if x]

        context.update({
            'survey_count': survey_count,
            'total_jobs': total_jobs,
            'survey_current': survey_current,
            'survey_future': survey_future,
            'latest_surveys': latest_surveys,
            'district_stats_json': json.dumps(district_stats),
            'block_stats_json': json.dumps(block_stats),
            'product_service_data_json': json.dumps(ps_data),
            'all_districts': all_districts,
            'all_blocks': all_blocks,
            'all_sectors': all_sectors,
            '_survey_sector_raw': survey_sector_raw,
        })
    except Exception as e:
        logger.error(f"Dashboard SURVEY error: {e}")
        traceback.print_exc()

    # ============================================================
    # 2. ASSOCIATION
    # ============================================================
    try:
        assoc_qs = AssociationConsultation.objects.all()
        if district_filter:
            assoc_qs = assoc_qs.filter(district_region__icontains=district_filter)
        if sector_filter:
            assoc_qs = assoc_qs.filter(primary_sector__icontains=sector_filter)

        assoc_count = assoc_qs.count()
        assoc_jobs_qs = AssociationJobRole.objects.filter(consultation__in=assoc_qs)
        association_jobs = assoc_jobs_qs.count()

        a_agg = assoc_jobs_qs.aggregate(
            cur=Coalesce(Sum('current_openings'), Value(0)),
            f6 =Coalesce(Sum('openings_6_months'), Value(0)),
            f12=Coalesce(Sum('openings_12_months'), Value(0)),
        )
        assoc_current = a_agg['cur']
        assoc_future  = a_agg['f6'] + a_agg['f12']

        latest_associations = []
        for ac in assoc_qs.prefetch_related('job_roles').order_by('-created_at')[:5]:
            total_demand = sum(
                (jr.current_openings or 0) + (jr.openings_6_months or 0) + (jr.openings_12_months or 0)
                for jr in ac.job_roles.all()
            )
            latest_associations.append({
                'id': ac.id,
                'consultation_id': ac.consultation_id or 'Draft',
                'association_name': ac.association_name or 'N/A',
                'district': ac.district_region or 'N/A',
                'primary_sector': ac.primary_sector or 'N/A',
                'total_demand': total_demand,
                'created_at': ac.created_at.strftime('%d %b %Y, %I:%M %p') if ac.created_at else '',
            })

        assoc_sector_raw = []
        for s in assoc_jobs_qs.values('sector').annotate(
            cur=Coalesce(Sum('current_openings'), Value(0)),
            fut=Coalesce(Sum(F('openings_6_months') + F('openings_12_months')), Value(0))
        ):
            if s['sector']:
                assoc_sector_raw.append({
                    'sector': s['sector'],
                    'current': s['cur'] or 0,
                    'future': s['fut'] or 0,
                })

        context.update({
            'association_count': assoc_count,
            'association_jobs': association_jobs,
            'association_current': assoc_current,
            'association_future': assoc_future,
            'latest_associations': latest_associations,
            '_assoc_sector_raw': assoc_sector_raw,
        })
    except Exception as e:
        logger.error(f"Dashboard ASSOCIATION error: {e}")
        traceback.print_exc()

    # ============================================================
    # 3. GOVERNMENT
    # ============================================================
    try:
        govt_qs = GovtConsultation.objects.all()
        if district_filter:
            govt_qs = govt_qs.filter(district_region__icontains=district_filter)

        govt_count = govt_qs.count()

        def _sum_govt_json(g):
            cur = fut = 0
            inv_total = 0.0
            try:
                occ = g.occupational_categories or []
                if isinstance(occ, str):
                    occ = json.loads(occ)
                for r in occ:
                    try:
                        cur += int(r.get('current_openings') or 0)
                        fut += int(r.get('projected_demand') or 0)
                    except (ValueError, TypeError):
                        pass
            except Exception:
                pass
            try:
                inv = g.investment_pipeline or []
                if isinstance(inv, str):
                    inv = json.loads(inv)
                for r in inv:
                    try:
                        inv_total += float(str(r.get('approx_investment') or 0).replace(',', ''))
                    except (ValueError, TypeError):
                        pass
            except Exception:
                pass
            return cur, fut, inv_total

        govt_current = govt_future = 0
        govt_investment = 0.0
        for g in govt_qs:
            c, f, i = _sum_govt_json(g)
            govt_current += c
            govt_future  += f
            govt_investment += i

        latest_govt = []
        for g in govt_qs.order_by('-created_at')[:5]:
            c, f, _ = _sum_govt_json(g)
            latest_govt.append({
                'id': g.id,
                'consultation_id': g.consultation_id or 'Draft',
                'respondent_name': g.respondent_name or 'N/A',
                'district': g.district_region or 'N/A',
                'current': c,
                'projected': f,
                'created_at': g.created_at.strftime('%d %b %Y, %I:%M %p') if g.created_at else '',
            })

        context.update({
            'govt_count': govt_count,
            'govt_current': govt_current,
            'govt_future': govt_future,
            'govt_investment': int(govt_investment),
            'latest_govt': latest_govt,
        })
    except Exception as e:
        logger.error(f"Dashboard GOVT error: {e}")
        traceback.print_exc()

    # ============================================================
    # 4. MERGE SECTOR (Survey + Association)
    # ============================================================
    try:
        merged = {}
        for s in context.get('_survey_sector_raw', []):
            merged[s['sector']] = {'current': s['current'], 'future': s['future']}
        for s in context.get('_assoc_sector_raw', []):
            if s['sector'] in merged:
                merged[s['sector']]['current'] += s['current']
                merged[s['sector']]['future']  += s['future']
            else:
                merged[s['sector']] = {'current': s['current'], 'future': s['future']}

        sector_data = [{'sector': k, 'current': v['current'], 'future': v['future']} for k, v in merged.items()]
        sector_data.sort(key=lambda x: -(x['current'] + x['future']))
        sector_data = sector_data[:10]

        context['sector_data_json'] = json.dumps(sector_data)
        context.pop('_survey_sector_raw', None)
        context.pop('_assoc_sector_raw', None)
    except Exception as e:
        logger.error(f"Dashboard SECTOR MERGE error: {e}")
        traceback.print_exc()

    # ============================================================
    # 5. COMBINED TOTALS + SOURCE BREAKDOWN
    # ============================================================
    context['total_surveys'] = (
        context['survey_count'] + context['association_count'] + context['govt_count']
    )
    context['total_current'] = (
        context['survey_current'] + context['association_current'] + context['govt_current']
    )
    context['total_future'] = (
        context['survey_future'] + context['association_future'] + context['govt_future']
    )

    source_breakdown = [
        {'source': 'Survey',      'count': context['survey_count'],
         'current': context['survey_current'], 'future': context['survey_future']},
        {'source': 'Association', 'count': context['association_count'],
         'current': context['association_current'], 'future': context['association_future']},
        {'source': 'Government',  'count': context['govt_count'],
         'current': context['govt_current'], 'future': context['govt_future']},
    ]
    context['source_breakdown_json'] = json.dumps(source_breakdown)

    return render(request, 'portal/dashboard.html', context)


@login_required
def admin_surveys(request):
    surveys = Survey.objects.all().prefetch_related('job_demands', 'apprenticeships')
    unique_districts = surveys.values_list('district', flat=True).distinct().count()
    total_jobs = JobDemand.objects.count()
    
    # Convert workforce_profile from JSON string to list if needed
    for survey in surveys:
        if isinstance(survey.workforce_profile, str):
            try:
                survey.workforce_profile = json.loads(survey.workforce_profile)
            except:
                survey.workforce_profile = []
    
    return render(request, 'portal/surveys.html', {
        'surveys': surveys,
        'total_jobs': total_jobs,
        'unique_districts': unique_districts,
    })
    
    
# ============================================
# EDIT/DELETE FUNCTIONS
# ============================================

@login_required
@csrf_exempt
def update_survey(request, survey_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body)
        survey = Survey.objects.get(id=survey_id)
        for key, value in data.items():
            if hasattr(survey, key):
                setattr(survey, key, value)
        survey.save()
        return JsonResponse({'status': 'success', 'message': 'Survey updated successfully'})
    except Survey.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Survey not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@csrf_exempt 
def delete_survey(request, survey_id):
    if request.method != 'DELETE':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    try:
        survey = Survey.objects.get(id=survey_id)
        if survey.supporting_document:
            if default_storage.exists(survey.supporting_document.name):
                default_storage.delete(survey.supporting_document.name)
        survey.delete()
        return JsonResponse({'status': 'success', 'message': 'Survey deleted successfully'})
    except Survey.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Survey not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@csrf_exempt
def update_job_demand(request, job_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body)
        job = JobDemand.objects.get(id=job_id)
        for key, value in data.items():
            if hasattr(job, key):
                setattr(job, key, value)
        job.save()
        return JsonResponse({'status': 'success', 'message': 'Job demand updated successfully'})
    except JobDemand.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Job demand not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@csrf_exempt 
def delete_job_demand(request, job_id):
    if request.method != 'DELETE':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    try:
        job = JobDemand.objects.get(id=job_id)
        job.delete()
        return JsonResponse({'status': 'success', 'message': 'Job demand deleted successfully'})
    except JobDemand.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Job demand not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@csrf_exempt
def update_apprenticeship(request, app_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body)
        app = ApprenticeshipOJT.objects.get(id=app_id)
        for key, value in data.items():
            if hasattr(app, key):
                setattr(app, key, value)
        app.save()
        return JsonResponse({'status': 'success', 'message': 'Apprenticeship updated successfully'})
    except ApprenticeshipOJT.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Apprenticeship not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@csrf_exempt 
def delete_apprenticeship(request, app_id):
    if request.method != 'DELETE':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    try:
        app = ApprenticeshipOJT.objects.get(id=app_id)
        app.delete()
        return JsonResponse({'status': 'success', 'message': 'Apprenticeship deleted successfully'})
    except ApprenticeshipOJT.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Apprenticeship not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def admin_job_demands(request):
    job_demands = JobDemand.objects.all().select_related('survey')
    total_current = job_demands.aggregate(total=Sum('current_openings'))['total'] or 0
    total_future_6 = job_demands.aggregate(total=Sum('openings_6_months'))['total'] or 0
    total_future_12 = job_demands.aggregate(total=Sum('openings_12_months'))['total'] or 0
    total_future = total_future_6 + total_future_12
    return render(request, 'portal/job_demands.html', {
        'job_demands': job_demands,
        'total_current': total_current,
        'total_future': total_future,
    })


@login_required
def admin_logout(request):
    logout(request)
    return redirect('survey:admin_login')


@login_required
def get_chart_data(request):
    total_current = JobDemand.objects.aggregate(total=Sum('current_openings'))['total'] or 0
    total_future_6 = JobDemand.objects.aggregate(total=Sum('openings_6_months'))['total'] or 0
    total_future_12 = JobDemand.objects.aggregate(total=Sum('openings_12_months'))['total'] or 0
    return JsonResponse({
        'current_demand': total_current,
        'future_demand': total_future_6 + total_future_12
    })


@login_required
def debug_data(request):
    surveys = Survey.objects.all()
    jobs = JobDemand.objects.all()
    data = {
        'survey_count': surveys.count(),
        'job_count': jobs.count(),
        'surveys': [{'id': s.id, 'company': s.company_name, 'code': s.company_code, 'jobs': s.job_demands.count()} for s in surveys],
        'jobs': [{'id': j.id, 'survey_id': j.survey_id, 'role': j.job_role, 'current': j.current_openings, 'future': j.openings_6_months + j.openings_12_months} for j in jobs]
    }
    return JsonResponse(data)


@login_required
def get_survey_detail(request, survey_id):
    try:
        survey = Survey.objects.get(id=survey_id)
        job_demands = survey.job_demands.all()
        apprenticeships = survey.apprenticeships.all()
        
        workforce_list = []
        try:
            if isinstance(survey.workforce_profile, str):
                workforce_list = json.loads(survey.workforce_profile) if survey.workforce_profile else []
            elif isinstance(survey.workforce_profile, list):
                workforce_list = survey.workforce_profile
        except:
            workforce_list = []
        
        data = {
            'id': survey.id,
            'company_code': survey.company_code or '',
            'company_name': survey.company_name,
            'organisation_type': survey.organisation_type,
            'organisation_type_other': survey.organisation_type_other or '',
            'product_service': survey.product_service,
            'product_service_specify': survey.product_service_specify or '',
            'operational_sector': survey.operational_sector,
            'operational_sector_other': survey.operational_sector_other or '',
            'company_size': survey.company_size or '',
            'district': survey.district,
            'block': survey.block,
            'address': survey.address,
            'website': survey.website or '',
            'contact_name': survey.contact_name,
            'contact_mobile': survey.contact_mobile,
            'contact_email': survey.contact_email,
            'has_hr': survey.has_hr,
            'workforce_profile': workforce_list,
            'placement_willingness': survey.placement_willingness,
            'apprenticeship_willingness': survey.apprenticeship_willingness,
            'guest_lecture_interest': survey.guest_lecture_interest,
            'industrial_visit_interest': survey.industrial_visit_interest,
            'csr_interest': survey.csr_interest,
            'ojt_internship_willingness': survey.ojt_internship_willingness,
            'recruitment_challenges': survey.recruitment_challenges or '',
            'additional_remarks': survey.additional_remarks or '',
            'supporting_evidence': survey.supporting_evidence or '',
            'supporting_document_url': survey.supporting_document.url if survey.supporting_document else '',
            'created_at': survey.created_at.strftime('%d %b %Y, %I:%M %p'),
            'submission_date': survey.submission_date.strftime('%Y-%m-%d') if survey.submission_date else '',
            'field_officer_name': survey.field_officer_name or '',
            
            'job_demands': [
                {
                    'row_no': job.row_no,
                    'job_role': job.job_role,
                    'sector': job.sector,
                    'qualification': job.qualification,
                    'qualification_other': job.qualification_other or '',
                    'experience': job.experience,
                    'certification': job.certification,
                    'certification_detail': job.certification_detail or '',
                    'salary_offered': job.salary_offered,
                    'current_openings': job.current_openings,
                    'openings_6_months': job.openings_6_months,
                    'openings_12_months': job.openings_12_months,
                    'apprentice_ojt': job.apprentice_ojt,
                    'apprentice_ojt_detail': job.apprentice_ojt_detail or '',
                    'gender_suitability': job.gender_suitability,
                    'pwd': job.pwd,
                    'career_progression': job.career_progression,
                    'career_progression_years': job.career_progression_years or '',
                    'career_next_position': job.career_next_position or '',
                    'career_next_salary': job.career_next_salary or '',
                    'additional_remarks': job.additional_remarks or ''
                }
                for job in job_demands
            ],
            
            'apprenticeships': [
                {
                    'row_no': app.row_no,
                    'job_role': app.job_role,
                    'opportunity_type': app.opportunity_type,
                    'seats_capacity': app.seats_capacity,
                    'duration_months': app.duration_months,
                    'monthly_stipend': app.monthly_stipend,
                    'expected_start_month': app.expected_start_month or '',
                    'minimum_qualification': app.minimum_qualification,
                    'minimum_qualification_other': app.minimum_qualification_other or '',
                    'conversion_to_employment': app.conversion_to_employment
                }
                for app in apprenticeships
            ],
            
            'totals': {
                'current_demand': survey.total_current_demand,
                'future_demand': survey.total_future_demand,
                'demand_6_months': survey.total_demand_6_months,
                'demand_12_months': survey.total_demand_12_months,
            }
        }
        return JsonResponse({'status': 'success', 'data': data})
    except Survey.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Survey not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def admin_export_full_csv(request):
    """Export complete survey data with all fields"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="survey_full_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    writer = csv.writer(response)
    
    main_headers = [
        'Survey ID', 'Company Code', 'Company Name', 
        'Organisation Type', 'Organisation Type (Other)',
        'Product / Service', 'Product / Service (Specify)',
        'Operational Sector', 'Operational Sector (Other)',
        'Company Size',
        'District', 'Block',
        'Address', 'Website',
        'Contact Name', 'Contact Mobile', 'Contact Email',
        'Has HR',
        'Field Officer Name', 'Field Officer Signature',
        'Placement Willingness', 'Apprenticeship Willingness',
        'Guest Lecture Interest', 'Industrial Visit Interest',
        'CSR Interest', 'OJT/Internship Willingness',
        'Recruitment Challenges', 'Additional Remarks', 
        'Supporting Evidence', 'Supporting Document',
        'Submission Date', 'Created At'
    ]
    
    max_workforce = 0
    for survey in Survey.objects.all():
        try:
            if isinstance(survey.workforce_profile, str):
                wf = json.loads(survey.workforce_profile) if survey.workforce_profile else []
            else:
                wf = survey.workforce_profile or []
            if len(wf) > max_workforce:
                max_workforce = len(wf)
        except:
            pass
    
    workforce_headers = []
    for i in range(1, max_workforce + 1):
        workforce_headers.extend([
            f'Workforce-{i} (Position)',
            f'Workforce-{i} (On Roll)',
            f'Workforce-{i} (Contractual)',
            f'Workforce-{i} (Apprentice/Interns)'
        ])
    
    max_jobs = JobDemand.objects.values('survey').annotate(job_count=Count('id')).aggregate(Max('job_count'))['job_count__max'] or 0
    job_headers = []
    for i in range(1, max_jobs + 1):
        job_headers.extend([
            f'Job Demand-{i} (Job Role)', f'Job Demand-{i} (Sector)',
            f'Job Demand-{i} (Qualification)', f'Job Demand-{i} (Qualification Other)',
            f'Job Demand-{i} (Experience)', f'Job Demand-{i} (Certification)',
            f'Job Demand-{i} (Certification Detail)', f'Job Demand-{i} (Salary Offered)',
            f'Job Demand-{i} (Current Openings)', f'Job Demand-{i} (6 Months)',
            f'Job Demand-{i} (12 Months)', f'Job Demand-{i} (Apprentice/OJT)',
            f'Job Demand-{i} (Apprentice/OJT Detail)', f'Job Demand-{i} (Gender Suitability)',
            f'Job Demand-{i} (PwD)', f'Job Demand-{i} (Career Progression)',
            f'Job Demand-{i} (Career Progression Years)', f'Job Demand-{i} (Career Next Position)',
            f'Job Demand-{i} (Career Next Salary)', f'Job Demand-{i} (Additional Remarks)'
        ])
    
    max_apps = ApprenticeshipOJT.objects.values('survey').annotate(app_count=Count('id')).aggregate(Max('app_count'))['app_count__max'] or 0
    app_headers = []
    for i in range(1, max_apps + 1):
        app_headers.extend([
            f'Apprenticeship-{i} (Job Role)', f'Apprenticeship-{i} (Opportunity Type)',
            f'Apprenticeship-{i} (Seats/Capacity)', f'Apprenticeship-{i} (Duration Months)',
            f'Apprenticeship-{i} (Monthly Stipend)', f'Apprenticeship-{i} (Expected Start Month)',
            f'Apprenticeship-{i} (Minimum Qualification)', f'Apprenticeship-{i} (Min Qualification Other)',
            f'Apprenticeship-{i} (Conversion to Employment)'
        ])
    
    total_headers = ['Total Current Demand', 'Total Future Demand', 'Total 6 Months Demand', 'Total 12 Months Demand']
    all_headers = main_headers + workforce_headers + job_headers + app_headers + total_headers
    writer.writerow(all_headers)
    
    for survey in Survey.objects.all().prefetch_related('job_demands', 'apprenticeships'):
        workforce_list = []
        try:
            if isinstance(survey.workforce_profile, str):
                workforce_list = json.loads(survey.workforce_profile) if survey.workforce_profile else []
            elif isinstance(survey.workforce_profile, list):
                workforce_list = survey.workforce_profile
        except:
            workforce_list = []
        
        row = [
            survey.id, survey.company_code or '', survey.company_name,
            survey.organisation_type or '', survey.organisation_type_other or '',
            survey.product_service or '', survey.product_service_specify or '',
            survey.operational_sector or '', survey.operational_sector_other or '',
            survey.company_size or '', survey.district or '', survey.block or '',
            survey.address or '', survey.website or '', survey.contact_name or '',
            survey.contact_mobile or '', survey.contact_email or '', survey.has_hr or 'No',
            survey.field_officer_name or '', survey.field_officer_signature or '',
            survey.placement_willingness or '', survey.apprenticeship_willingness or '',
            survey.guest_lecture_interest or '', survey.industrial_visit_interest or '',
            survey.csr_interest or '', survey.ojt_internship_willingness or '',
            survey.recruitment_challenges or '', survey.additional_remarks or '',
            survey.supporting_evidence or '', survey.supporting_document.name if survey.supporting_document else '',
            survey.submission_date.strftime('%Y-%m-%d') if survey.submission_date else '',
            survey.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ]
        
        for i in range(max_workforce):
            if i < len(workforce_list):
                w = workforce_list[i]
                row.extend([w.get('position', ''), w.get('onroll', 0), w.get('contractual', 0), w.get('apprentice', 0)])
            else:
                row.extend([''] * 4)
        
        job_list = list(survey.job_demands.all())
        for i in range(max_jobs):
            if i < len(job_list):
                job = job_list[i]
                row.extend([
                    job.job_role, job.sector, job.qualification, job.qualification_other or '',
                    job.experience, job.certification, job.certification_detail or '',
                    job.salary_offered, job.current_openings, job.openings_6_months,
                    job.openings_12_months, job.apprentice_ojt, job.apprentice_ojt_detail or '',
                    job.gender_suitability, job.pwd, job.career_progression,
                    job.career_progression_years or '', job.career_next_position or '',
                    job.career_next_salary or '', job.additional_remarks or ''
                ])
            else:
                row.extend([''] * 20)
        
        app_list = list(survey.apprenticeships.all())
        for i in range(max_apps):
            if i < len(app_list):
                app = app_list[i]
                row.extend([
                    app.job_role, app.opportunity_type, app.seats_capacity,
                    app.duration_months, app.monthly_stipend, app.expected_start_month or '',
                    app.minimum_qualification, app.minimum_qualification_other or '',
                    app.conversion_to_employment
                ])
            else:
                row.extend([''] * 9)
        
        row.extend([survey.total_current_demand, survey.total_future_demand, survey.total_demand_6_months, survey.total_demand_12_months])
        writer.writerow(row)
    return response


# ============================================
# NEW ASSOCIATION VIEWS
# ============================================

def association_form(request):
    return render(request, 'association_form.html')


@csrf_exempt
@require_http_methods(["POST"])
def submit_association(request):
    print("="*60)
    print("🔵 SUBMIT ASSOCIATION API CALLED")
    print("="*60)
    
    try:
        if request.content_type and 'multipart/form-data' in request.content_type:
            data = request.POST.dict()
            files = request.FILES
        else:
            data = json.loads(request.body)
            files = {}
        
        print(f"✅ Data Parsed Successfully")
        
        with transaction.atomic():
            consultation_date = data.get('consultation_date')
            if consultation_date:
                consultation_date = datetime.strptime(consultation_date, '%Y-%m-%d').date()
            else:
                consultation_date = datetime.now().date()
            
            submission_date = data.get('submission_date')
            if submission_date:
                submission_date = datetime.strptime(submission_date, '%Y-%m-%d').date()
            else:
                submission_date = datetime.now().date()
            
            recruitment_challenges = data.get('recruitment_challenges', '[]')
            if isinstance(recruitment_challenges, str):
                try:
                    recruitment_challenges = json.loads(recruitment_challenges)
                except:
                    recruitment_challenges = []
            
            consultation = AssociationConsultation.objects.create(
                consultation_id=data.get('consultation_id', '').strip(),
                district_region=data.get('district_region', '').strip(),
                mode=data.get('mode', '').strip(),
                mode_other=data.get('mode_other', '').strip(),
                consultation_date=consultation_date,
                surveyor_name=data.get('surveyor_name', '').strip(),
                association_name=data.get('association_name', '').strip(),
                association_type=data.get('association_type', '').strip(),
                association_type_other=data.get('association_type_other', '').strip(),
                primary_sector=data.get('primary_sector', '').strip(),
                geographic_coverage=data.get('geographic_coverage', '').strip(),
                geographic_specify=data.get('geographic_specify', '').strip(),
                year_established=int(data.get('year_established', 0)) if data.get('year_established') else None,
                total_members=int(data.get('total_members', 0)) if data.get('total_members') else None,
                active_members=int(data.get('active_members', 0)) if data.get('active_members') else None,
                comp_micro=int(data.get('comp_micro', 0)) if data.get('comp_micro') else None,
                comp_small=int(data.get('comp_small', 0)) if data.get('comp_small') else None,
                comp_medium=int(data.get('comp_medium', 0)) if data.get('comp_medium') else None,
                comp_large=int(data.get('comp_large', 0)) if data.get('comp_large') else None,
                key_clusters=data.get('key_clusters', '').strip(),
                respondent_name=data.get('respondent_name', '').strip(),
                respondent_mobile=data.get('respondent_mobile', '').strip(),
                respondent_email=data.get('respondent_email', '').strip(),
                major_products=data.get('major_products', '').strip(),
                estimated_workforce=int(data.get('estimated_workforce', 0)) if data.get('estimated_workforce') else None,
                business_trend=data.get('business_trend', '').strip(),
                growth_drivers=data.get('growth_drivers', '').strip(),
                upcoming_projects=data.get('upcoming_projects', '').strip(),
                peak_hiring=data.get('peak_hiring', '').strip(),
                member_employers_count=int(data.get('member_employers_count', 0)) if data.get('member_employers_count') else None,
                member_list_attached=data.get('member_list_attached') == 'on' or data.get('member_list_attached') == 'true',
                recruitment_challenges=recruitment_challenges,
                difficult_roles=data.get('difficult_roles', '').strip(),
                emerging_roles=data.get('emerging_roles', '').strip(),
                changing_competencies=data.get('changing_competencies', '').strip(),
                skill_gaps=data.get('skill_gaps', '').strip(),
                high_demand_districts=data.get('high_demand_districts', '').strip(),
                unfilled_reasons=data.get('unfilled_reasons', '').strip(),
                mobilise_placements=data.get('mobilise_placements', '').strip(),
                support_apprenticeship=data.get('support_apprenticeship', '').strip(),
                support_guest_lectures=data.get('support_guest_lectures', '').strip(),
                facilitate_visits=data.get('facilitate_visits', '').strip(),
                demand_updates=data.get('demand_updates', '').strip(),
                nodal_officer_name=data.get('nodal_officer_name', '').strip(),
                nodal_officer_mobile=data.get('nodal_officer_mobile', '').strip(),
                nodal_officer_email=data.get('nodal_officer_email', '').strip(),
                survey_reviewed=data.get('survey_reviewed', '').strip(),
                alignment_view=data.get('alignment_view', '').strip(),
                priority_training=data.get('priority_training', '').strip(),
                curriculum_changes=data.get('curriculum_changes', '').strip(),
                placement_actions=data.get('placement_actions', '').strip(),
                policy_support=data.get('policy_support', '').strip(),
                additional_remarks=data.get('additional_remarks', '').strip(),
                supporting_evidence=data.get('supporting_evidence', ''), # Fixed removed strip
                demand_evidence_status=data.get('demand_evidence_status', '').strip(),
                respondent_signature=data.get('respondent_signature', '').strip(),
                facilitator_signature=data.get('facilitator_signature', '').strip(),
                submission_date=submission_date,
            )
            
            print(f"✅ Consultation Created! ID: {consultation.id}")
            
            if 'supporting_document' in files:
                uploaded_file = files['supporting_document']
                if uploaded_file.size > 50 * 1024:
                    return JsonResponse({'status': 'error', 'message': 'File size exceeds 50KB limit.'}, status=400)
                
                file_name = f"assoc_{consultation.id}_{uploaded_file.name}"
                saved_path = default_storage.save(
                    os.path.join('association_documents', file_name),
                    ContentFile(uploaded_file.read())
                )
                consultation.supporting_document = saved_path
                consultation.save()
            
            job_roles_data = data.get('job_demands', '[]')
            if isinstance(job_roles_data, str):
                try:
                    job_roles_data = json.loads(job_roles_data)
                except:
                    job_roles_data = []
            
            for idx, job_data in enumerate(job_roles_data, 1):
                mobility = job_data.get('mobility', [])
                if isinstance(mobility, str):
                    try:
                        mobility = json.loads(mobility)
                    except:
                        mobility = []
                
                AssociationJobRole.objects.create(
                    consultation=consultation,
                    row_no=idx,
                    job_role=job_data.get('job_role', '').strip(),
                    sector=job_data.get('sector', '').strip(),
                    location=job_data.get('location', '').strip(),
                    qualification=job_data.get('qualification', '').strip(),
                    qualification_other=job_data.get('qualification_other', '').strip(),
                    experience=job_data.get('experience', '').strip(),
                    certification=job_data.get('certification', 'No'),
                    certification_detail=job_data.get('certification_detail', '').strip(),
                    salary=job_data.get('salary', '').strip(),
                    salary_period=job_data.get('salary_period', '').strip(),
                    employment_type=job_data.get('employment_type', '').strip(),
                    current_openings=int(job_data.get('current_openings') or 0), # Fixed int crash
                    openings_6_months=int(job_data.get('openings_6_months') or 0),
                    openings_12_months=int(job_data.get('openings_12_months') or 0),
                    tech_skills=job_data.get('tech_skills', '').strip(),
                    employability_skills=job_data.get('employability_skills', '').strip(),
                    women_suitable=job_data.get('women_suitable', 'Yes'),
                    pwd=job_data.get('pwd', 'Yes'),
                    mobility=mobility,
                    apprentice_seats=int(job_data.get('apprentice_seats') or 0),
                    ojt_seats=int(job_data.get('ojt_seats') or 0),
                    internship_seats=int(job_data.get('internship_seats') or 0),
                    reporting_employers=int(job_data.get('reporting_employers') or 0),
                    employer_list_attached=job_data.get('employer_list_attached', False),
                    remarks=job_data.get('remarks', '').strip()
                )
            
            apprenticeships_data = data.get('apprenticeships', '[]')
            if isinstance(apprenticeships_data, str):
                try:
                    apprenticeships_data = json.loads(apprenticeships_data)
                except:
                    apprenticeships_data = []
            
            for idx, app_data in enumerate(apprenticeships_data, 1):
                AssociationApprenticeship.objects.create(
                    consultation=consultation,
                    row_no=idx,
                    job_role=app_data.get('job_role', '').strip(),
                    opportunity_type=app_data.get('opportunity_type', '').strip(),
                    employers_interested=int(app_data.get('employers_interested') or 0),
                    seats=int(app_data.get('seats') or 0),
                    duration=int(app_data.get('duration') or 0),
                    stipend=app_data.get('stipend', '').strip(),
                    start_period=app_data.get('start_period', '').strip(),
                    conversion=app_data.get('conversion', 'Not known'),
                    employer_list=app_data.get('employer_list', 'No')
                )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Association consultation submitted successfully',
            'consultation_id': consultation.id
        }, status=201)
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        traceback.print_exc()
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


def _to_int(value, default=None):
    if value in (None, '', 'None'):
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _serialize_consultation(consultation):
    """Detail + Edit view dono ke liye JSON-safe dict."""
    job_roles = consultation.job_roles.all()
    apprenticeships = consultation.apprenticeship_opportunities.all()
    return {
        'id': consultation.id,
        'consultation_id': consultation.consultation_id or '',
        'district_region': consultation.district_region,
        'mode': consultation.mode,
        'mode_other': consultation.mode_other or '',
        'consultation_date': consultation.consultation_date.strftime('%Y-%m-%d') if consultation.consultation_date else '',
        'surveyor_name': consultation.surveyor_name,
        'association_name': consultation.association_name,
        'association_type': consultation.association_type,
        'association_type_other': consultation.association_type_other or '',
        'primary_sector': consultation.primary_sector,
        'geographic_coverage': consultation.geographic_coverage,
        'geographic_specify': consultation.geographic_specify or '',
        'year_established': consultation.year_established,
        'total_members': consultation.total_members,
        'active_members': consultation.active_members,
        'comp_micro': consultation.comp_micro,
        'comp_small': consultation.comp_small,
        'comp_medium': consultation.comp_medium,
        'comp_large': consultation.comp_large,
        'key_clusters': consultation.key_clusters or '',
        'respondent_name': consultation.respondent_name,
        'respondent_mobile': consultation.respondent_mobile,
        'respondent_email': consultation.respondent_email,
        'major_products': consultation.major_products or '',
        'estimated_workforce': consultation.estimated_workforce,
        'business_trend': consultation.business_trend or '',
        'growth_drivers': consultation.growth_drivers or '',
        'upcoming_projects': consultation.upcoming_projects or '',
        'peak_hiring': consultation.peak_hiring or '',
        'member_employers_count': consultation.member_employers_count,
        'member_list_attached': consultation.member_list_attached,
        'recruitment_challenges': consultation.recruitment_challenges or [],
        'difficult_roles': consultation.difficult_roles or '',
        'emerging_roles': consultation.emerging_roles or '',
        'changing_competencies': consultation.changing_competencies or '',
        'skill_gaps': consultation.skill_gaps or '',
        'high_demand_districts': consultation.high_demand_districts or '',
        'unfilled_reasons': consultation.unfilled_reasons or '',
        'mobilise_placements': consultation.mobilise_placements or '',
        'support_apprenticeship': consultation.support_apprenticeship or '',
        'support_guest_lectures': consultation.support_guest_lectures or '',
        'facilitate_visits': consultation.facilitate_visits or '',
        'demand_updates': consultation.demand_updates or '',
        'nodal_officer_name': consultation.nodal_officer_name or '',
        'nodal_officer_mobile': consultation.nodal_officer_mobile or '',
        'nodal_officer_email': consultation.nodal_officer_email or '',
        'survey_reviewed': consultation.survey_reviewed or '',
        'alignment_view': consultation.alignment_view or '',
        'priority_training': consultation.priority_training or '',
        'curriculum_changes': consultation.curriculum_changes or '',
        'placement_actions': consultation.placement_actions or '',
        'policy_support': consultation.policy_support or '',
        'additional_remarks': consultation.additional_remarks or '',
        'supporting_evidence': consultation.supporting_evidence or '',
        'demand_evidence_status': consultation.demand_evidence_status or '',
        'respondent_signature': consultation.respondent_signature or '',
        'facilitator_signature': consultation.facilitator_signature or '',
        'submission_date': consultation.submission_date.strftime('%Y-%m-%d') if consultation.submission_date else '',
        'supporting_document_url': consultation.supporting_document.url if consultation.supporting_document else '',
        'created_at': consultation.created_at.strftime('%d %b %Y, %I:%M %p'),
        'job_roles': [
            {
                'row_no': job.row_no,
                'job_role': job.job_role,
                'sector': job.sector or '',
                'location': job.location or '',
                'qualification': job.qualification or '',
                'qualification_other': job.qualification_other or '',
                'experience': job.experience or '',
                'certification': job.certification,
                'certification_detail': job.certification_detail or '',
                'salary': job.salary or '',
                'salary_period': job.salary_period or '',
                'employment_type': job.employment_type or '',
                'current_openings': job.current_openings,
                'openings_6_months': job.openings_6_months,
                'openings_12_months': job.openings_12_months,
                'tech_skills': job.tech_skills or '',
                'employability_skills': job.employability_skills or '',
                'women_suitable': job.women_suitable,
                'pwd': job.pwd,
                'mobility': job.mobility or [],
                'apprentice_seats': job.apprentice_seats,
                'ojt_seats': job.ojt_seats,
                'internship_seats': job.internship_seats,
                'reporting_employers': job.reporting_employers,
                'employer_list_attached': job.employer_list_attached,
                'remarks': job.remarks or '',
            }
            for job in job_roles
        ],
        'apprenticeships': [
            {
                'row_no': app.row_no,
                'job_role': app.job_role,
                'opportunity_type': app.opportunity_type,
                'employers_interested': app.employers_interested,
                'seats': app.seats,
                'duration': app.duration,
                'stipend': app.stipend or '',
                'start_period': app.start_period or '',
                'conversion': app.conversion,
                'employer_list': app.employer_list,
            }
            for app in apprenticeships
        ],
        'totals': {
            'total_job_roles': job_roles.count(),
            'total_apprenticeships': apprenticeships.count(),
            'total_current_demand': consultation.total_current_demand,
            'total_future_demand': consultation.total_future_demand,
        },
    }


@login_required
def admin_association_list(request):
    # Efficient aggregates via Subquery (avoids N+1 and join double-count)
    jr_stats = AssociationJobRole.objects.filter(consultation=OuterRef('pk')).values('consultation').annotate(
        cnt=Count('*'),
        cur=Coalesce(Sum('current_openings'), Value(0)),
        fut=Coalesce(Sum(F('openings_6_months') + F('openings_12_months')), Value(0)),
    )
    app_stats = AssociationApprenticeship.objects.filter(consultation=OuterRef('pk')).values('consultation').annotate(
        cnt=Count('*'),
    )

    consultations = AssociationConsultation.objects.annotate(
        job_role_count=Coalesce(Subquery(jr_stats.values('cnt')), Value(0)),
        current_demand_sum=Coalesce(Subquery(jr_stats.values('cur')), Value(0)),
        future_demand_sum=Coalesce(Subquery(jr_stats.values('fut')), Value(0)),
        apprenticeship_count=Coalesce(Subquery(app_stats.values('cnt')), Value(0)),
    ).prefetch_related('job_roles', 'apprenticeship_opportunities')

    context = {
        'consultations': consultations,
        'total_consultations': consultations.count(),
        'total_job_roles': AssociationJobRole.objects.count(),
        'total_apprenticeships': AssociationApprenticeship.objects.count(),
    }
    return render(request, 'portal/association_list.html', context)


@login_required
def get_association_detail(request, consultation_id):
    try:
        consultation = AssociationConsultation.objects.prefetch_related(
            'job_roles', 'apprenticeship_opportunities'
        ).get(id=consultation_id)
        data = _serialize_consultation(consultation)
        return JsonResponse({'status': 'success', 'data': data})
    except AssociationConsultation.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Consultation not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def admin_association_edit(request, consultation_id):
    """Admin-only edit page — renders the public form template in edit mode."""
    try:
        consultation = AssociationConsultation.objects.prefetch_related(
            'job_roles', 'apprenticeship_opportunities'
        ).get(id=consultation_id)
    except AssociationConsultation.DoesNotExist:
        messages.error(request, 'Consultation not found.')
        return redirect('survey:admin_association_list')

    data = _serialize_consultation(consultation)
    context = {
        'edit_mode': True,
        'consultation_id': consultation.id,
        'consultation_data_json': json.dumps(data),
    }
    # 👇 path fix — existing public template use karo
    return render(request, 'association_form.html', context)


@login_required
def admin_association_update(request, consultation_id):
    """Update an existing consultation — keeps the same ID / consultation_id."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    try:
        consultation = AssociationConsultation.objects.get(id=consultation_id)
    except AssociationConsultation.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Consultation not found'}, status=404)

    try:
        with transaction.atomic():
            d = request.POST

            # ---- Section A ----
            new_cid = (d.get('consultation_id') or '').strip()
            if new_cid:
                consultation.consultation_id = new_cid
            consultation.district_region = d.get('district_region', consultation.district_region)
            consultation.mode = d.get('mode', consultation.mode)
            consultation.mode_other = d.get('mode_other', '')
            if d.get('consultation_date'):
                parsed = parse_date(d.get('consultation_date'))
                if parsed:
                    consultation.consultation_date = parsed
            consultation.surveyor_name = d.get('surveyor_name', consultation.surveyor_name)

            # ---- Section B ----
            consultation.association_name = d.get('association_name', consultation.association_name)
            consultation.association_type = d.get('association_type', consultation.association_type)
            consultation.association_type_other = d.get('association_type_other', '')
            consultation.primary_sector = d.get('primary_sector', consultation.primary_sector)
            consultation.geographic_coverage = d.get('geographic_coverage', consultation.geographic_coverage)
            consultation.geographic_specify = d.get('geographic_specify', '')
            consultation.year_established = _to_int(d.get('year_established'))
            consultation.total_members = _to_int(d.get('total_members'))
            consultation.active_members = _to_int(d.get('active_members'))
            consultation.key_clusters = d.get('key_clusters', '')
            consultation.comp_micro = _to_int(d.get('comp_micro'))
            consultation.comp_small = _to_int(d.get('comp_small'))
            consultation.comp_medium = _to_int(d.get('comp_medium'))
            consultation.comp_large = _to_int(d.get('comp_large'))
            consultation.respondent_name = d.get('respondent_name', consultation.respondent_name)
            consultation.respondent_mobile = d.get('respondent_mobile', consultation.respondent_mobile)
            consultation.respondent_email = d.get('respondent_email', consultation.respondent_email)

            # ---- Section C ----
            consultation.major_products = d.get('major_products', '')
            consultation.estimated_workforce = _to_int(d.get('estimated_workforce'))
            consultation.business_trend = d.get('business_trend', '')
            consultation.growth_drivers = d.get('growth_drivers', '')
            consultation.upcoming_projects = d.get('upcoming_projects', '')
            consultation.peak_hiring = d.get('peak_hiring', '')
            consultation.member_employers_count = _to_int(d.get('member_employers_count'))
            consultation.member_list_attached = bool(d.get('member_list_attached'))

            # ---- Section F ----
            try:
                consultation.recruitment_challenges = json.loads(d.get('recruitment_challenges', '[]'))
            except (json.JSONDecodeError, TypeError):
                consultation.recruitment_challenges = []
            consultation.difficult_roles = d.get('difficult_roles', '')
            consultation.emerging_roles = d.get('emerging_roles', '')
            consultation.changing_competencies = d.get('changing_competencies', '')
            consultation.skill_gaps = d.get('skill_gaps', '')
            consultation.high_demand_districts = d.get('high_demand_districts', '')
            consultation.unfilled_reasons = d.get('unfilled_reasons', '')

            # ---- Section G ----
            consultation.mobilise_placements = d.get('mobilise_placements', '')
            consultation.support_apprenticeship = d.get('support_apprenticeship', '')
            consultation.support_guest_lectures = d.get('support_guest_lectures', '')
            consultation.facilitate_visits = d.get('facilitate_visits', '')
            consultation.demand_updates = d.get('demand_updates', '')
            consultation.nodal_officer_name = d.get('nodal_officer_name', '')
            consultation.nodal_officer_mobile = d.get('nodal_officer_mobile', '')
            consultation.nodal_officer_email = d.get('nodal_officer_email', '')

            # ---- Section H ----
            consultation.survey_reviewed = d.get('survey_reviewed', '')
            consultation.alignment_view = d.get('alignment_view', '')
            consultation.priority_training = d.get('priority_training', '')
            consultation.curriculum_changes = d.get('curriculum_changes', '')
            consultation.placement_actions = d.get('placement_actions', '')
            consultation.policy_support = d.get('policy_support', '')
            consultation.additional_remarks = d.get('additional_remarks', '')

            # ---- Section I ----
            consultation.supporting_evidence = d.get('supporting_evidence', '')
            consultation.demand_evidence_status = d.get('demand_evidence_status', '')
            consultation.respondent_signature = d.get('respondent_signature', '')
            consultation.facilitator_signature = d.get('facilitator_signature', '')
            if d.get('submission_date'):
                parsed = parse_date(d.get('submission_date'))
                if parsed:
                    consultation.submission_date = parsed

            if 'supporting_document' in request.FILES:
                new_file = request.FILES['supporting_document']
                if new_file and new_file.size > 0:
                    if consultation.supporting_document and default_storage.exists(consultation.supporting_document.name):
                        default_storage.delete(consultation.supporting_document.name)
                    consultation.supporting_document = new_file

            consultation.save()

            # ---- Replace job roles ----
            consultation.job_roles.all().delete()
            try:
                job_demands = json.loads(d.get('job_demands', '[]'))
            except (json.JSONDecodeError, TypeError):
                job_demands = []

            for idx, jd in enumerate(job_demands, start=1):
                AssociationJobRole.objects.create(
                    consultation=consultation,
                    row_no=idx,
                    job_role=jd.get('job_role', ''),
                    sector=jd.get('sector', ''),
                    location=jd.get('location', ''),
                    qualification=jd.get('qualification', ''),
                    qualification_other=jd.get('qualification_other', ''),
                    experience=jd.get('experience', ''),
                    certification=jd.get('certification', 'No'),
                    certification_detail=jd.get('certification_detail', ''),
                    salary=jd.get('salary', ''),
                    salary_period=jd.get('salary_period', ''),
                    employment_type=jd.get('employment_type', ''),
                    current_openings=_to_int(jd.get('current_openings'), 0),
                    openings_6_months=_to_int(jd.get('openings_6_months'), 0),
                    openings_12_months=_to_int(jd.get('openings_12_months'), 0),
                    tech_skills=jd.get('tech_skills', ''),
                    employability_skills=jd.get('employability_skills', ''),
                    women_suitable=jd.get('women_suitable', ''),
                    pwd=jd.get('pwd', ''),
                    mobility=jd.get('mobility', []),
                    apprentice_seats=_to_int(jd.get('apprentice_seats'), 0),
                    ojt_seats=_to_int(jd.get('ojt_seats'), 0),
                    internship_seats=_to_int(jd.get('internship_seats'), 0),
                    reporting_employers=_to_int(jd.get('reporting_employers'), 0),
                    employer_list_attached=bool(jd.get('employer_list_attached')),
                    remarks=jd.get('remarks', ''),
                )

            # ---- Replace apprenticeships ----
            consultation.apprenticeship_opportunities.all().delete()
            try:
                apprenticeships = json.loads(d.get('apprenticeships', '[]'))
            except (json.JSONDecodeError, TypeError):
                apprenticeships = []

            for idx, app in enumerate(apprenticeships, start=1):
                AssociationApprenticeship.objects.create(
                    consultation=consultation,
                    row_no=idx,
                    job_role=app.get('job_role', ''),
                    opportunity_type=app.get('opportunity_type', ''),
                    employers_interested=_to_int(app.get('employers_interested'), 0),
                    seats=_to_int(app.get('seats'), 0),
                    duration=_to_int(app.get('duration'), 0),
                    stipend=app.get('stipend', ''),
                    start_period=app.get('start_period', ''),
                    conversion=app.get('conversion', ''),
                    employer_list=app.get('employer_list', ''),
                )

        return JsonResponse({'status': 'success', 'message': 'Consultation updated successfully'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def delete_association(request, consultation_id):
    if request.method != 'DELETE':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    try:
        consultation = AssociationConsultation.objects.get(id=consultation_id)
        if consultation.supporting_document and default_storage.exists(consultation.supporting_document.name):
            default_storage.delete(consultation.supporting_document.name)
        consultation.delete()
        return JsonResponse({'status': 'success', 'message': 'Consultation deleted successfully'})
    except AssociationConsultation.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Consultation not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def admin_export_association_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="association_consultations_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'Consultation ID', 'Date', 'Association Name', 'Association Type', 'Primary Sector',
        'District/Region', 'Surveyor Name', 'Respondent Name', 'Respondent Mobile',
        'Total Members', 'Active Members', 'Business Trend', 'Total Job Roles',
        'Total Current Demand', 'Total Future Demand', 'Total Apprenticeships',
        'Created At'
    ])
    for c in AssociationConsultation.objects.all():
        writer.writerow([
            c.consultation_id or '',
            c.consultation_date.strftime('%Y-%m-%d') if c.consultation_date else '',
            c.association_name, c.association_type, c.primary_sector, c.district_region,
            c.surveyor_name, c.respondent_name, c.respondent_mobile,
            c.total_members or 0, c.active_members or 0, c.business_trend or '',
            c.total_job_roles, c.total_current_demand, c.total_future_demand,
            c.total_apprenticeships,
            c.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        ])
    return response


# ============================================================
# GOVERNMENT DEPARTMENT CONSULTATION VIEWS
# ============================================================

def govt_form(request):
    return render(request, 'govt_form.html')


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def submit_govt(request):
    print("=" * 60)
    print("🔵 SUBMIT GOVT CONSULTATION API CALLED")
    print("=" * 60)

    if request.method == "OPTIONS":
        return JsonResponse({'status': 'ok'}, status=200)

    try:
        files = {}
        content_type = (request.content_type or '').lower()

        if 'multipart/form-data' in content_type:
            data = request.POST.dict()
            files = request.FILES
        elif 'application/json' in content_type:
            try:
                data = json.loads(request.body)
            except Exception as je:
                return JsonResponse({'status': 'error', 'message': f'Invalid JSON: {je}'}, status=400)
        else:
            if request.POST:
                data = request.POST.dict()
                files = request.FILES
            else:
                try:
                    data = json.loads(request.body or b'{}')
                except Exception as fe:
                    return JsonResponse({'status': 'error', 'message': 'Unsupported or malformed request body.'}, status=400)

        def parse_json_field(field_name, default=None):
            if default is None:
                default = []
            val = data.get(field_name, default)
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except Exception:
                    return default
            return val if val is not None else default

        consultation_date = data.get('consultation_date', '').strip()
        if consultation_date:
            try:
                consultation_date = datetime.strptime(consultation_date, '%Y-%m-%d').date()
            except ValueError:
                consultation_date = datetime.now().date()
        else:
            consultation_date = datetime.now().date()

        submission_date = data.get('submission_date', '').strip()
        if submission_date:
            try:
                submission_date = datetime.strptime(submission_date, '%Y-%m-%d').date()
            except ValueError:
                submission_date = datetime.now().date()
        else:
            submission_date = datetime.now().date()

        office_visited = parse_json_field('office_visited')
        body_type = parse_json_field('body_type')
        jurisdiction = parse_json_field('jurisdiction')
        investment_pipeline = parse_json_field('investment_pipeline')
        sectoral_analysis = parse_json_field('sectoral_analysis')
        occupational_categories = parse_json_field('occupational_categories')
        facilitation_mode = parse_json_field('facilitation_mode')
        recruitment_challenges = parse_json_field('recruitment_challenges')
        supporting_evidence = parse_json_field('supporting_evidence')

        aware_count = data.get('aware_establishments_count', '').strip()
        try:
            aware_count = int(aware_count) if aware_count else None
        except (ValueError, TypeError):
            aware_count = None

        required_fields = {
            'consultation_id': 'Consultation ID',
            'district_region': 'District / Region',
            'mode': 'Mode of Consultation',
            'surveyor_name': 'Surveyor Name',
            'respondent_name': 'Respondent Name',
            'respondent_mobile': 'Respondent Mobile',
            'respondent_email': 'Respondent Email',
        }
        missing = []
        for key, label in required_fields.items():
            if not str(data.get(key, '')).strip():
                missing.append(label)

        if missing:
            return JsonResponse({'status': 'error', 'message': f'Missing required fields: {", ".join(missing)}'}, status=400)

        with transaction.atomic():
            consultation = GovtConsultation.objects.create(
                consultation_id=data.get('consultation_id', '').strip(),
                district_region=data.get('district_region', '').strip(),
                mode=data.get('mode', '').strip(),
                mode_other=data.get('mode_other', '').strip(),
                consultation_date=consultation_date,
                surveyor_name=data.get('surveyor_name', '').strip(),
                office_visited=office_visited,
                office_visited_other=data.get('office_visited_other', '').strip(),
                body_type=body_type,
                body_type_other=data.get('body_type_other', '').strip(),
                jurisdiction=jurisdiction,
                jurisdiction_other=data.get('jurisdiction_other', '').strip(),
                respondent_name=data.get('respondent_name', '').strip(),
                respondent_mobile=data.get('respondent_mobile', '').strip(),
                respondent_email=data.get('respondent_email', '').strip(),
                office_address=data.get('office_address', '').strip(),
                department_website=data.get('department_website', '').strip(),
                nodal_officer_name=data.get('nodal_officer_name', '').strip(),
                nodal_officer_mobile=data.get('nodal_officer_mobile', '').strip(),
                nodal_officer_email=data.get('nodal_officer_email', '').strip(),
                investment_pipeline=investment_pipeline,
                sectoral_analysis=sectoral_analysis,
                occupational_categories=occupational_categories,
                upcoming_schemes=data.get('upcoming_schemes', '').strip(),
                emerging_technologies=data.get('emerging_technologies', '').strip(),
                aware_establishments=data.get('aware_establishments', '').strip(),
                can_facilitate=data.get('can_facilitate', '').strip(),
                aware_establishments_count=aware_count,
                concentration_sectors=data.get('concentration_sectors', '').strip(),
                known_employers=data.get('known_employers', '').strip(),
                facilitation_mode=facilitation_mode,
                recruitment_challenges=recruitment_challenges,
                difficult_roles=data.get('difficult_roles', '').strip(),
                emerging_roles=data.get('emerging_roles', '').strip(),
                changing_competencies=data.get('changing_competencies', '').strip(),
                skill_gaps=data.get('skill_gaps', '').strip(),
                high_demand_districts=data.get('high_demand_districts', '').strip(),
                unfilled_reasons=data.get('unfilled_reasons', '').strip(),
                operational_challenges=data.get('operational_challenges', '').strip(),
                facilitate_surveys=data.get('facilitate_surveys', '').strip(),
                share_registration_data=data.get('share_registration_data', '').strip(),
                participate_coordination=data.get('participate_coordination', '').strip(),
                share_demand_updates=data.get('share_demand_updates', '').strip(),
                dept_nodal_officer_name=data.get('dept_nodal_officer_name', '').strip(),
                dept_nodal_officer_mobile=data.get('dept_nodal_officer_mobile', '').strip(),
                dept_nodal_officer_email=data.get('dept_nodal_officer_email', '').strip(),
                supporting_evidence=supporting_evidence,
                demand_evidence_status=data.get('demand_evidence_status', '').strip(),
                submission_date=submission_date,
                place=data.get('place', '').strip(),
                authorized_signature=data.get('authorized_signature', '').strip(),
                respondent_signature=data.get('respondent_signature', '').strip(),
                official_stamp=(str(data.get('official_stamp', '')).lower() in ['true', 'on', '1', 'yes']),
            )

            if 'supporting_document' in files:
                uploaded_file = files['supporting_document']
                if uploaded_file.size > 50 * 1024:
                    raise ValueError('File size exceeds 50KB limit.')
                file_name = f"govt_{consultation.id}_{uploaded_file.name}"
                saved_path = default_storage.save(
                    os.path.join('govt_documents', file_name),
                    ContentFile(uploaded_file.read())
                )
                consultation.supporting_document = saved_path
                consultation.save()

        return JsonResponse({
            'status': 'success',
            'message': 'Government consultation submitted successfully',
            'consultation_id': consultation.id
        }, status=201)

    except ValueError as ve:
        return JsonResponse({'status': 'error', 'message': str(ve)}, status=400)
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': f'{type(e).__name__}: {str(e)}'}, status=500)

def _serialize_govt(consultation):
    """Serialize GovtConsultation for edit-form prefill."""
    def ensure_list(val):
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            try:
                return json.loads(val)
            except Exception:
                return []
        return []

    return {
        'id': consultation.id,
        'consultation_id': consultation.consultation_id or '',
        'district_region': consultation.district_region or '',
        'mode': consultation.mode or '',
        'mode_other': consultation.mode_other or '',
        'consultation_date': consultation.consultation_date.strftime('%Y-%m-%d') if consultation.consultation_date else '',
        'surveyor_name': consultation.surveyor_name or '',
        'office_visited': ensure_list(consultation.office_visited),
        'office_visited_other': consultation.office_visited_other or '',
        'body_type': ensure_list(consultation.body_type),
        'body_type_other': consultation.body_type_other or '',
        'jurisdiction': ensure_list(consultation.jurisdiction),
        'jurisdiction_other': consultation.jurisdiction_other or '',
        'respondent_name': consultation.respondent_name or '',
        'respondent_mobile': consultation.respondent_mobile or '',
        'respondent_email': consultation.respondent_email or '',
        'office_address': consultation.office_address or '',
        'department_website': consultation.department_website or '',
        'nodal_officer_name': consultation.nodal_officer_name or '',
        'nodal_officer_mobile': consultation.nodal_officer_mobile or '',
        'nodal_officer_email': consultation.nodal_officer_email or '',
        'investment_pipeline': ensure_list(consultation.investment_pipeline),
        'sectoral_analysis': ensure_list(consultation.sectoral_analysis),
        'occupational_categories': ensure_list(consultation.occupational_categories),
        'upcoming_schemes': consultation.upcoming_schemes or '',
        'emerging_technologies': consultation.emerging_technologies or '',
        'aware_establishments': consultation.aware_establishments or '',
        'can_facilitate': consultation.can_facilitate or '',
        'aware_establishments_count': consultation.aware_establishments_count,
        'concentration_sectors': consultation.concentration_sectors or '',
        'known_employers': consultation.known_employers or '',
        'facilitation_mode': ensure_list(consultation.facilitation_mode),
        'recruitment_challenges': ensure_list(consultation.recruitment_challenges),
        'difficult_roles': consultation.difficult_roles or '',
        'emerging_roles': consultation.emerging_roles or '',
        'changing_competencies': consultation.changing_competencies or '',
        'skill_gaps': consultation.skill_gaps or '',
        'high_demand_districts': consultation.high_demand_districts or '',
        'unfilled_reasons': consultation.unfilled_reasons or '',
        'operational_challenges': consultation.operational_challenges or '',
        'facilitate_surveys': consultation.facilitate_surveys or '',
        'share_registration_data': consultation.share_registration_data or '',
        'participate_coordination': consultation.participate_coordination or '',
        'share_demand_updates': consultation.share_demand_updates or '',
        'dept_nodal_officer_name': consultation.dept_nodal_officer_name or '',
        'dept_nodal_officer_mobile': consultation.dept_nodal_officer_mobile or '',
        'dept_nodal_officer_email': consultation.dept_nodal_officer_email or '',
        'supporting_evidence': ensure_list(consultation.supporting_evidence),
        'demand_evidence_status': consultation.demand_evidence_status or '',
        'submission_date': consultation.submission_date.strftime('%Y-%m-%d') if consultation.submission_date else '',
        'place': consultation.place or '',
        'authorized_signature': consultation.authorized_signature or '',
        'respondent_signature': consultation.respondent_signature or '',
        'official_stamp': consultation.official_stamp,
        'supporting_document_url': consultation.supporting_document.url if consultation.supporting_document else '',
    }

@login_required
def admin_govt_list(request):
    consultations = GovtConsultation.objects.all()
    context = {
        'consultations': consultations,
        'total_consultations': consultations.count(),
        'total_investment': sum(c.total_investment_pipeline for c in consultations),
        'total_current_openings': sum(c.total_current_openings for c in consultations),
        'total_projected_demand': sum(c.total_occupational_demand for c in consultations),
    }
    return render(request, 'portal/govt_list.html', context)


@login_required
def get_govt_detail(request, consultation_id):
    try:
        consultation = GovtConsultation.objects.get(id=consultation_id)

        def ensure_list(val):
            if isinstance(val, list):
                return val
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except:
                    return []
            return []

        data = {
            'id': consultation.id,
            'consultation_id': consultation.consultation_id or '',
            'district_region': consultation.district_region,
            'mode': consultation.mode,
            'mode_other': consultation.mode_other or '',
            'consultation_date': consultation.consultation_date.strftime('%Y-%m-%d') if consultation.consultation_date else '',
            'surveyor_name': consultation.surveyor_name,
            'office_visited': ensure_list(consultation.office_visited),
            'office_visited_other': consultation.office_visited_other or '',
            'body_type': ensure_list(consultation.body_type),
            'body_type_other': consultation.body_type_other or '',
            'jurisdiction': ensure_list(consultation.jurisdiction),
            'jurisdiction_other': consultation.jurisdiction_other or '',
            'respondent_name': consultation.respondent_name,
            'respondent_mobile': consultation.respondent_mobile,
            'respondent_email': consultation.respondent_email,
            'office_address': consultation.office_address or '',
            'department_website': consultation.department_website or '',
            'nodal_officer_name': consultation.nodal_officer_name or '',
            'nodal_officer_mobile': consultation.nodal_officer_mobile or '',
            'nodal_officer_email': consultation.nodal_officer_email or '',
            'investment_pipeline': ensure_list(consultation.investment_pipeline),
            'sectoral_analysis': ensure_list(consultation.sectoral_analysis),
            'occupational_categories': ensure_list(consultation.occupational_categories),
            'upcoming_schemes': consultation.upcoming_schemes or '',
            'emerging_technologies': consultation.emerging_technologies or '',
            'aware_establishments': consultation.aware_establishments or '',
            'can_facilitate': consultation.can_facilitate or '',
            'aware_establishments_count': consultation.aware_establishments_count,
            'concentration_sectors': consultation.concentration_sectors or '',
            'known_employers': consultation.known_employers or '',
            'facilitation_mode': ensure_list(consultation.facilitation_mode),
            'recruitment_challenges': ensure_list(consultation.recruitment_challenges),
            'difficult_roles': consultation.difficult_roles or '',
            'emerging_roles': consultation.emerging_roles or '',
            'changing_competencies': consultation.changing_competencies or '',
            'skill_gaps': consultation.skill_gaps or '',
            'high_demand_districts': consultation.high_demand_districts or '',
            'unfilled_reasons': consultation.unfilled_reasons or '',
            'operational_challenges': consultation.operational_challenges or '',
            'facilitate_surveys': consultation.facilitate_surveys or '',
            'share_registration_data': consultation.share_registration_data or '',
            'participate_coordination': consultation.participate_coordination or '',
            'share_demand_updates': consultation.share_demand_updates or '',
            'dept_nodal_officer_name': consultation.dept_nodal_officer_name or '',
            'dept_nodal_officer_mobile': consultation.dept_nodal_officer_mobile or '',
            'dept_nodal_officer_email': consultation.dept_nodal_officer_email or '',
            'supporting_evidence': ensure_list(consultation.supporting_evidence),
            'demand_evidence_status': consultation.demand_evidence_status or '',
            'submission_date': consultation.submission_date.strftime('%Y-%m-%d') if consultation.submission_date else '',
            'place': consultation.place or '',
            'authorized_signature': consultation.authorized_signature or '',
            'respondent_signature': consultation.respondent_signature or '',
            'official_stamp': consultation.official_stamp,
            'supporting_document_url': consultation.supporting_document.url if consultation.supporting_document else '',
            'created_at': consultation.created_at.strftime('%d %b %Y, %I:%M %p'),
            'totals': {
                'investment_pipeline': consultation.total_investment_pipeline,
                'current_openings': consultation.total_current_openings,
                'projected_demand': consultation.total_occupational_demand,
            }
        }
        return JsonResponse({'status': 'success', 'data': data})
    except GovtConsultation.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Consultation not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def admin_govt_edit(request, consultation_id):
    """Render govt_form.html pre-filled with existing consultation data."""
    try:
        consultation = GovtConsultation.objects.get(id=consultation_id)
    except GovtConsultation.DoesNotExist:
        messages.error(request, 'Consultation not found.')
        return redirect('survey:admin_govt_list')

    data = _serialize_govt(consultation)
    context = {
        'edit_mode': True,
        'consultation_id': consultation.id,
        'consultation_data_json': json.dumps(data),
    }
    return render(request, 'govt_form.html', context)


@login_required
def admin_govt_update(request, consultation_id):
    """Update existing govt consultation — same ID retained."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    try:
        consultation = GovtConsultation.objects.get(id=consultation_id)
    except GovtConsultation.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Consultation not found'}, status=404)

    try:
        data = request.POST.dict()
        files = request.FILES

        def parse_json_field(field_name, default=None):
            if default is None:
                default = []
            val = data.get(field_name, default)
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except Exception:
                    return default
            return val if val is not None else default

        # ---- Dates ----
        if data.get('consultation_date'):
            try:
                consultation.consultation_date = datetime.strptime(
                    data.get('consultation_date'), '%Y-%m-%d').date()
            except ValueError:
                pass
        if data.get('submission_date'):
            try:
                consultation.submission_date = datetime.strptime(
                    data.get('submission_date'), '%Y-%m-%d').date()
            except ValueError:
                pass

        # ---- Section A ----
        if data.get('consultation_id', '').strip():
            consultation.consultation_id = data.get('consultation_id').strip()
        consultation.district_region = data.get('district_region', consultation.district_region)
        consultation.mode = data.get('mode', consultation.mode)
        consultation.mode_other = data.get('mode_other', '')
        consultation.surveyor_name = data.get('surveyor_name', consultation.surveyor_name)
        consultation.office_visited = parse_json_field('office_visited')
        consultation.office_visited_other = data.get('office_visited_other', '')

        # ---- Section B ----
        consultation.body_type = parse_json_field('body_type')
        consultation.body_type_other = data.get('body_type_other', '')
        consultation.jurisdiction = parse_json_field('jurisdiction')
        consultation.jurisdiction_other = data.get('jurisdiction_other', '')
        consultation.respondent_name = data.get('respondent_name', consultation.respondent_name)
        consultation.respondent_mobile = data.get('respondent_mobile', consultation.respondent_mobile)
        consultation.respondent_email = data.get('respondent_email', consultation.respondent_email)
        consultation.office_address = data.get('office_address', '')
        consultation.department_website = data.get('department_website', '')
        consultation.nodal_officer_name = data.get('nodal_officer_name', '')
        consultation.nodal_officer_mobile = data.get('nodal_officer_mobile', '')
        consultation.nodal_officer_email = data.get('nodal_officer_email', '')

        # ---- Section C / D ----
        consultation.investment_pipeline = parse_json_field('investment_pipeline')
        consultation.sectoral_analysis = parse_json_field('sectoral_analysis')

        # ---- Section E ----
        consultation.occupational_categories = parse_json_field('occupational_categories')
        consultation.upcoming_schemes = data.get('upcoming_schemes', '')
        consultation.emerging_technologies = data.get('emerging_technologies', '')
        consultation.aware_establishments = data.get('aware_establishments', '')
        consultation.can_facilitate = data.get('can_facilitate', '')
        aware_count = data.get('aware_establishments_count', '').strip()
        try:
            consultation.aware_establishments_count = int(aware_count) if aware_count else None
        except (ValueError, TypeError):
            consultation.aware_establishments_count = None
        consultation.concentration_sectors = data.get('concentration_sectors', '')
        consultation.known_employers = data.get('known_employers', '')
        consultation.facilitation_mode = parse_json_field('facilitation_mode')

        # ---- Section F ----
        consultation.recruitment_challenges = parse_json_field('recruitment_challenges')
        consultation.difficult_roles = data.get('difficult_roles', '')
        consultation.emerging_roles = data.get('emerging_roles', '')
        consultation.changing_competencies = data.get('changing_competencies', '')
        consultation.skill_gaps = data.get('skill_gaps', '')
        consultation.high_demand_districts = data.get('high_demand_districts', '')
        consultation.unfilled_reasons = data.get('unfilled_reasons', '')
        consultation.operational_challenges = data.get('operational_challenges', '')

        # ---- Section G ----
        consultation.facilitate_surveys = data.get('facilitate_surveys', '')
        consultation.share_registration_data = data.get('share_registration_data', '')
        consultation.participate_coordination = data.get('participate_coordination', '')
        consultation.share_demand_updates = data.get('share_demand_updates', '')
        consultation.dept_nodal_officer_name = data.get('dept_nodal_officer_name', '')
        consultation.dept_nodal_officer_mobile = data.get('dept_nodal_officer_mobile', '')
        consultation.dept_nodal_officer_email = data.get('dept_nodal_officer_email', '')

        # ---- Section H ----
        consultation.supporting_evidence = parse_json_field('supporting_evidence')
        consultation.demand_evidence_status = data.get('demand_evidence_status', '')
        consultation.place = data.get('place', '')
        consultation.authorized_signature = data.get('authorized_signature', '')
        consultation.respondent_signature = data.get('respondent_signature', '')
        consultation.official_stamp = (
            str(data.get('official_stamp', '')).lower() in ['true', 'on', '1', 'yes']
        )

        # ---- New file (only replace if user uploaded) ----
        if 'supporting_document' in files:
            uploaded_file = files['supporting_document']
            if uploaded_file.size > 50 * 1024:
                return JsonResponse({'status': 'error', 'message': 'File size exceeds 50KB limit.'}, status=400)
            if consultation.supporting_document and default_storage.exists(consultation.supporting_document.name):
                default_storage.delete(consultation.supporting_document.name)
            file_name = f"govt_{consultation.id}_{uploaded_file.name}"
            consultation.supporting_document = default_storage.save(
                os.path.join('govt_documents', file_name),
                ContentFile(uploaded_file.read())
            )

        consultation.save()
        return JsonResponse({'status': 'success', 'message': 'Government consultation updated successfully'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'{type(e).__name__}: {str(e)}'}, status=500)

@login_required
def delete_govt(request, consultation_id):
    if request.method != 'DELETE':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    try:
        consultation = GovtConsultation.objects.get(id=consultation_id)
        if consultation.supporting_document:
            if default_storage.exists(consultation.supporting_document.name):
                default_storage.delete(consultation.supporting_document.name)
        consultation.delete()
        return JsonResponse({'status': 'success', 'message': 'Consultation deleted successfully'})
    except GovtConsultation.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Consultation not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def admin_export_govt_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="govt_consultations_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    writer = csv.writer(response)

    def ensure_list(val):
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            try:
                return json.loads(val)
            except Exception:
                return []
        return []

    def get_max_rows(field_name):
        max_rows = 0
        for c in GovtConsultation.objects.all():
            rows = ensure_list(getattr(c, field_name, []))
            if isinstance(rows, list) and len(rows) > max_rows:
                max_rows = len(rows)
        return max_rows

    max_inv_rows = get_max_rows('investment_pipeline')
    max_sector_rows = get_max_rows('sectoral_analysis')
    max_occ_rows = get_max_rows('occupational_categories')

    main_headers = [
        'Consultation ID', 'District / Region', 'Mode', 'Mode (Other)',
        'Consultation Date', 'Surveyor Name', 'Office Visited', 'Office Visited (Other)',
        'Body Type', 'Body Type (Other)', 'Jurisdiction', 'Jurisdiction (Other)',
        'Respondent Name', 'Respondent Mobile', 'Respondent Email',
        'Office Address', 'Department Website', 'Nodal Officer Name', 'Nodal Officer Mobile',
        'Nodal Officer Email', 'E.2 Upcoming Schemes', 'E.3 Emerging Technologies',
        'Aware of Establishments', 'Can Facilitate', 'Approx. No. of Such Establishments',
        'Concentration Sectors', 'Known Employers', 'Facilitation Mode', 'Recruitment Challenges',
        'Most Difficult-to-Fill Roles', 'Emerging Job Roles', 'Changing Technical Competencies',
        'Employability Skill Gaps', 'Districts / Clusters with Highest Demand', 'Reasons for Unfilled Vacancies',
        'Manpower & Operational Challenges', 'Facilitate Employer Surveys', 'Share Registration Data',
        'Participate in Coordination', 'Share Periodic Demand Updates', 'Dept. Nodal Officer Name',
        'Dept. Nodal Officer Mobile', 'Dept. Nodal Officer Email', 'Supporting Evidence',
        'Demand Evidence Status', 'Submission Date', 'Place', 'Authorized Signature',
        'Respondent Signature', 'Official Stamp', 'Supporting Document',
        'Total Investment Pipeline (₹ Cr)', 'Total Current Openings', 'Total Projected Demand', 'Created At'
    ]

    inv_headers = []
    for i in range(1, max_inv_rows + 1):
        inv_headers.extend([
            f'Investment-{i} (Sector Classification)', f'Investment-{i} (Dominant / Existing Sectors)',
            f'Investment-{i} (Emerging Sectors)', f'Investment-{i} (Approx. Investment ₹ Cr)',
            f'Investment-{i} (Specific District)'
        ])

    sector_headers = []
    for i in range(1, max_sector_rows + 1):
        sector_headers.extend([
            f'Sectoral-{i} (Sector Classification)', f'Sectoral-{i} (Dominant / Existing Sectors)',
            f'Sectoral-{i} (Emerging Sectors)'
        ])

    occ_headers = []
    for i in range(1, max_occ_rows + 1):
        occ_headers.extend([
            f'Occupational-{i} (Category / Role)', f'Occupational-{i} (Sector)',
            f'Occupational-{i} (Minimum Qualification)', f'Occupational-{i} (Est. Current Openings)',
            f'Occupational-{i} (Projected Demand 12 Mo)', f'Occupational-{i} (Indicative Wage ₹/Month)'
        ])

    all_headers = main_headers + inv_headers + sector_headers + occ_headers
    writer.writerow(all_headers)

    def list_to_str(val):
        if isinstance(val, list):
            return ', '.join(str(v) for v in val if v not in (None, ''))
        return str(val or '')

    for c in GovtConsultation.objects.all():
        row = [
            c.consultation_id or '', c.district_region or '', c.mode or '', c.mode_other or '',
            c.consultation_date.strftime('%Y-%m-%d') if c.consultation_date else '',
            c.surveyor_name or '', list_to_str(ensure_list(c.office_visited)), c.office_visited_other or '',
            list_to_str(ensure_list(c.body_type)), c.body_type_other or '',
            list_to_str(ensure_list(c.jurisdiction)), c.jurisdiction_other or '',
            c.respondent_name or '', c.respondent_mobile or '', c.respondent_email or '',
            c.office_address or '', c.department_website or '', c.nodal_officer_name or '',
            c.nodal_officer_mobile or '', c.nodal_officer_email or '', c.upcoming_schemes or '',
            c.emerging_technologies or '', c.aware_establishments or '', c.can_facilitate or '',
            c.aware_establishments_count if c.aware_establishments_count is not None else '',
            c.concentration_sectors or '', c.known_employers or '',
            list_to_str(ensure_list(c.facilitation_mode)), list_to_str(ensure_list(c.recruitment_challenges)),
            c.difficult_roles or '', c.emerging_roles or '', c.changing_competencies or '',
            c.skill_gaps or '', c.high_demand_districts or '', c.unfilled_reasons or '',
            c.operational_challenges or '', c.facilitate_surveys or '', c.share_registration_data or '',
            c.participate_coordination or '', c.share_demand_updates or '',
            c.dept_nodal_officer_name or '', c.dept_nodal_officer_mobile or '', c.dept_nodal_officer_email or '',
            list_to_str(ensure_list(c.supporting_evidence)), c.demand_evidence_status or '',
            c.submission_date.strftime('%Y-%m-%d') if c.submission_date else '',
            c.place or '', c.authorized_signature or '', c.respondent_signature or '',
            'Yes' if c.official_stamp else 'No',
            c.supporting_document.name if c.supporting_document else '',
            c.total_investment_pipeline, c.total_current_openings, c.total_occupational_demand,
            c.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        ]

        inv_rows = ensure_list(c.investment_pipeline)
        for i in range(max_inv_rows):
            if i < len(inv_rows):
                r = inv_rows[i] or {}
                row.extend([r.get('sector_classification', '') or '', r.get('dominant_sectors', '') or '', r.get('emerging_sectors', '') or '', r.get('approx_investment', '') or '', r.get('specific_district', '') or ''])
            else:
                row.extend([''] * 5)

        sector_rows = ensure_list(c.sectoral_analysis)
        for i in range(max_sector_rows):
            if i < len(sector_rows):
                r = sector_rows[i] or {}
                row.extend([r.get('sector_classification', '') or '', r.get('dominant_sectors', '') or '', r.get('emerging_sectors', '') or ''])
            else:
                row.extend([''] * 3)

        occ_rows = ensure_list(c.occupational_categories)
        for i in range(max_occ_rows):
            if i < len(occ_rows):
                r = occ_rows[i] or {}
                row.extend([r.get('category', '') or '', r.get('sector', '') or '', r.get('qualification', '') or '', r.get('current_openings', 0) if r.get('current_openings') is not None else 0, r.get('projected_demand', 0) if r.get('projected_demand') is not None else 0, r.get('wage_range', '') or ''])
            else:
                row.extend([''] * 6)

        writer.writerow(row)
    return response