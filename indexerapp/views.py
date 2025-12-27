from django.shortcuts import render, get_object_or_404
from django.views import View

# Create your views here.
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, authenticate


from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Manuscripts, AttributeDebate, Decoration, Content, Formulas, Subjects, Characteristics, DecorationTechniques, RiteNames, ManuscriptMusicNotations, Provenance, Codicology, Layouts, TimeReference, Bibliography, EditionContent, BindingTypes, BindingStyles, BindingMaterials, Colours, Clla, Projects, MSProjects, DecorationTypes, BindingDecorationTypes, BindingComponents, Binding, ManuscriptBindingComponents,  UserOpenAIAPIKey, ImproveOurDataEntry, Traditions, LiturgicalGenres, Genre, MusicNotationNames
from django.http import JsonResponse
from django.contrib.contenttypes.models import ContentType

from django.forms.models import model_to_dict

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

#from django_serverside_datatable.views import ServerSideDatatableView

from .serializers import *

from dal import autocomplete

from pyzotero import zotero

from django.http import JsonResponse
from rest_framework import viewsets

#for admin url creation:
from django.urls import reverse
import re

import math

#For filtering only specific columns:
from django.db.models import Q
from django_filters import filters
from rest_framework_datatables.django_filters.backends import DatatablesFilterBackend
from rest_framework_datatables.django_filters.filterset import DatatablesFilterSet
from rest_framework_datatables.django_filters.filters import GlobalFilter
from django.db.models import Count

#For sorting nulls last:
from django.db.models import F




#For assistant:
from django.db import connection
#from dubo import generate_sql
import os
from .ai_tools import process_ai_query
import threading
from .models import AIQuery  # Add this import


#For content importer:
from decimal import Decimal
import json
from django.apps import apps
from django.db import models

from iommi import Page, Form, Table

#For graph generation:
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io

#For TEI:
from xml.etree.ElementTree import Element, SubElement, tostring
#For TEI XML Template:
from django.views.generic import TemplateView
from django.template.loader import render_to_string


#for Registration:
from django.contrib.auth.models import User, Group

#for logout:
from django.contrib.auth import logout

#for password change
from django.contrib.auth import update_session_auth_hash

#for api key getter setter
from django.contrib.auth.decorators import login_required

#for data export
import csv

#from zotero.forms import get_tag_formset

#For Suggestions captcha form:
from django.views.generic.edit import CreateView

from captcha.models import CaptchaStore
from captcha.helpers import captcha_image_url


#For traditions assignment:
from django.db import transaction



ZOTERO_library_type = 'group'
#ZOTERO_api_key = 'HhPM6AN8emREftJShQBRITeI' #'5hnxe02vaDuZJ8O4qkUAT6Ty'
#ZOTERO_library_id = 5244710

ZOTERO_api_key = '5hnxe02vaDuZJ8O4qkUAT6Ty'
#ZOTERO_library_id = 12744975
ZOTERO_library_id = 5244710 #group id

class Login(View):
    template = 'login.html'

    def get(self, request):
        form = AuthenticationForm()
        return render(request, self.template, {'form': form})


    def post(self, request):
        form = AuthenticationForm(request.POST)
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return HttpResponseRedirect('/static/page.html?p=manuscripts')
        else:
            return render(request, self.template, {'form': form})


@method_decorator(csrf_exempt, name='dispatch')
class AjaxLoginView(View):
    def post(self, request, *args, **kwargs):
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'Invalid credentials'})

class LogoutView(View):
    def get(self, request, *args, **kwargs):
        logout(request)
        #return redirect('/login')
        return HttpResponseRedirect('/static/login.html')


class AjaxChangePasswordView(View):
    def post(self, request, *args, **kwargs):
        new_password = request.POST.get('new_password')

        if not self.validate_password(new_password):
            return JsonResponse({'success': False, 'error': 'Password must be at least 10 characters long, contain both uppercase and lowercase letters, and at least one number.'})

        user = request.user
        user.set_password(new_password)
        user.save()
        update_session_auth_hash(request, user)  # To keep the user logged in after password change

        return JsonResponse({'success': True})

    def validate_password(self, password):
        import re
        if len(password) < 10:
            return False
        if not re.search(r'[A-Z]', password):
            return False
        if not re.search(r'[a-z]', password):
            return False
        if not re.search(r'[0-9]', password):
            return False
        return True


@method_decorator(csrf_exempt, name='dispatch')
class AjaxRegisterView(View):
    def post(self, request, *args, **kwargs):
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        if User.objects.filter(username=username).exists():
            return JsonResponse({'success': False, 'error': 'Username already taken.'})

        if User.objects.filter(email=email).exists():
            return JsonResponse({'success': False, 'error': 'Email already registered.'})

        if not self.validate_password(password):
            return JsonResponse({'success': False, 'error': 'Password must be at least 10 characters long, contain both uppercase and lowercase letters, and at least one number.'})

        user = User.objects.create_user(username=username, email=email, password=password)
        user.save()

        # Add user to "views-only" group
        views_only_group, created = Group.objects.get_or_create(name='views-only')
        user.groups.add(views_only_group)

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'Authentication failed after registration.'})

    def validate_password(self, password):
        import re
        if len(password) < 10:
            return False
        if not re.search(r'[A-Z]', password):
            return False
        if not re.search(r'[a-z]', password):
            return False
        if not re.search(r'[0-9]', password):
            return False
        return True



@method_decorator(csrf_exempt, name='dispatch')
class GetAPIKeyView(View):
    @method_decorator(login_required)
    def get(self, request, *args, **kwargs):
        try:
            user_api_key = UserOpenAIAPIKey.objects.get(user=request.user)
            return JsonResponse({'success': True, 'api_key': user_api_key.api_key})
        except UserOpenAIAPIKey.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'API key not found.'})

@method_decorator(csrf_exempt, name='dispatch')
class SetAPIKeyView(View):
    @method_decorator(login_required)
    def post(self, request, *args, **kwargs):
        api_key = request.POST.get('api_key')
        if not api_key:
            return JsonResponse({'success': False, 'error': 'API key cannot be empty.'})
        
        user_api_key, created = UserOpenAIAPIKey.objects.get_or_create(user=request.user)
        user_api_key.api_key = api_key
        user_api_key.save()
        
        return JsonResponse({'success': True})





class MainInfoAjaxView(View):
    def get(self, request, *args, **kwargs):
        # Assuming you want to retrieve the username from the currently logged-in user
        print(request.user);

        username = request.user.get_username()
        groups = list(request.user.groups.values_list('name', flat=True))
        
        # Check if user is a superuser
        is_superuser = request.user.is_superuser
        is_staff = request.user.is_staff

        edit_mode = False
        if hasattr(request.user, "profile"):
            edit_mode = request.user.profile.edit_mode

        # Define the list of permissions to check
        permissions_to_check = [
            'add_manuscripts',
            'add_content',
            'add_bibliography',
            'add_editioncontent',
            'add_formulas',
            'add_manuscripts',  # Duplicate permission 'add_manuscripts' is listed twice, is this intentional?
            'add_ritenames',
            'add_timereference'
        ]

        # Check each permission
        #permissions = {perm: request.user.has_perm(f'app_label.{perm}') for perm in permissions_to_check}

        # Check if user has all the specified permissions
        import_permissions = all(request.user.has_perm(f'app_label.{perm}') for perm in permissions_to_check)

        # Prepare the data to be returned in the JSON response
        data = {
            'username': username,
            'groups': groups,
            'is_superuser': is_superuser,
            'is_staff': is_staff,
            'import_permissions': import_permissions,
            'edit_mode': edit_mode
        }
        return JsonResponse(data)


class MSInfoAjaxView(View):
    def get(self, request, *args, **kwargs):
        # Get the manuscript instance using the provided ID (pk)
        manuscript_id = self.request.GET.get('pk')
        instance = get_object_or_404(Manuscripts, id=manuscript_id)

        # Main info
        info = get_obj_dictionary(instance, [])

        #authors_names = [str(author) for author in instance.authors.all()]
        #info['authors']=authors_names

        print("This is MSInfoAjaxView")
        #print("This is info ms_genres:", info.ms_genres)
        print("This is instance ms_genres:", instance.ms_genres.all())

        info['ms_genres'] = [str(genre.genre) for genre in instance.ms_genres.all()]



        # Manuscript comments (debate)
        debate = AttributeDebate.objects.filter(content_type__model='manuscripts', object_id=manuscript_id)
        debate_data = []

        # Iterate over each debate object
        for d in debate:
            # Find the Bibliography object associated with the bibliography_id
            bibliography = Bibliography.objects.get(id=d.bibliography_id)
            
            # Create a dictionary with debate details
            debate_dict = {
                'id': d.id,
                'field_name': d.field_name,
                'text': d.text,
                'bibliography': str(bibliography),  # String representation of the Bibliography name
                'bibliography_id': d.bibliography_id 
            }
            
            # Append the dictionary to the debate_data list
            debate_data.append(debate_dict)

        # Create the response dictionary
        data = {
            'manuscript': info,
            'debate': debate_data,  # Convert QuerySet to a list for JSON serialization
        }

        return JsonResponse(data)


class GlobalCharFilter(GlobalFilter, filters.CharFilter):
    pass

class GlobalNumberFilter(GlobalFilter, filters.NumberFilter):
    pass

class CustomDatatablesFilterBackend(DatatablesFilterBackend):
    #help(rest_framework_datatables.django_filters.backends)
    #help(DatatablesFilterBackend)

    def filter_queryset(self, request, queryset, view):
        queryset = super().filter_queryset(request, queryset, view)
        
        where_min = request.query_params.get('where_min')
        where_max = request.query_params.get('where_max')

        print(where_min)
        print(where_min)

        if where_min is not None:
            queryset = queryset.filter(where_in_ms_from__gte=where_min)
        
        if where_max is not None:
            queryset = queryset.filter(where_in_ms_from__lte=where_max)

        
        ##Order
        order_column_index = int(request.query_params.get('order[0][column]', 0))
        order_column_name = request.query_params.get(f'columns[{order_column_index}][data]', 'name')
        order_direction = request.query_params.get('order[0][dir]', 'asc')
        print("--------------------------------------------")
        print(order_column_index)
        print(order_column_name)
        print(order_direction)
        print("--------------------------------------------")
        # Apply ordering to queryset
        if order_direction == 'asc':
            queryset = queryset.order_by(order_column_name)
        else:
            queryset = queryset.order_by(f'-{order_column_name}')

        return queryset

class ContentGlobalFilter(DatatablesFilterSet):
    """Filter name, artist and genre by name with icontains"""

    'manuscript', 'formula', 'rubric', 'rubric_name_from_ms', 'formula_text', 'sequence_in_ms', 'where_in_ms_from', 'where_in_ms_to', 'similarity_by_user', 'similarity_levenshtein' 

    manuscript = filters.NumberFilter(lookup_expr='exact')


    #manuscript = GlobalCharFilter(lookup_expr='icontains')
    #formula = GlobalCharFilter(field_name='formula__text', lookup_expr='icontains')
    rubric_name_from_ms = GlobalCharFilter(field_name='rubric_name_from_ms', lookup_expr='icontains')
    formula_text = GlobalCharFilter(field_name='formula_text', lookup_expr='icontains')
    sequence_in_ms = GlobalCharFilter()
    where_in_ms_from = GlobalNumberFilter(field_name='where_in_ms_from', lookup_expr='gt')
    where_in_ms_to = GlobalNumberFilter(field_name='where_in_ms_to', lookup_expr='lt')

    class Meta:
        model = Content
        fields = '__all__'


class ContentViewSet(viewsets.ModelViewSet):
    queryset = Content.objects.all().order_by('manuscript')
    serializer_class = ContentSerializer
    filter_backends = [CustomDatatablesFilterBackend]
    filterset_class = ContentGlobalFilter

    def get_queryset(self):
        queryset = Content.objects.filter(manuscript__display_as_main=True)
        manuscript_id = self.request.GET.get('manuscript_id', None)
        if manuscript_id:
            queryset = queryset.filter(manuscript_id=manuscript_id)
            
        #I want to send only if sequence_in_ms is not null or comments is not null
        queryset = queryset.filter(Q(sequence_in_ms__isnull=False) | Q(comments__isnull=False))
        
        order_column_name = self.request.query_params.get('order_column', 'manuscript')
        order_direction = self.request.query_params.get('order_direction', 'asc')
        if order_direction == 'asc':
            queryset = queryset.order_by(F(order_column_name).asc(nulls_last=True))
        else:
            queryset = queryset.order_by(F(order_column_name).desc(nulls_last=True))
        
        return queryset

    def count(self, request, queryset):
        return queryset.count()

    """
    def get_queryset(self):
        manuscript_id = self.request.GET.get('manuscript_id', None)
        if manuscript_id:
            return Content.objects.filter(manuscript_id=manuscript_id).order_by('manuscript')
        else:
            return Content.objects.all().order_by('manuscript')
    """

class ManuscriptHandsViewSet(viewsets.ModelViewSet):
    serializer_class = ManuscriptHandsSerializer
    filter_backends = [DatatablesFilterBackend]

    def get_queryset(self):
        is_main_text_param = self.request.query_params.get('is_main_text')
        manuscript_id_param = self.request.query_params.get('ms')
        
        # Convert is_main_text_param to a boolean value
        is_main_text = True if is_main_text_param == "true" else False if is_main_text_param == "false" else None
        
        queryset = ManuscriptHands.objects.all()
        
        # Apply the filter for is_main_text if provided
        if is_main_text is not None:
            queryset = queryset.filter(is_main_text=is_main_text)
        
        # Apply the filter for manuscript_id if provided
        if manuscript_id_param is not None:
            queryset = queryset.filter(manuscript_id=manuscript_id_param)
        
        return queryset

class ManuscriptsViewSet(viewsets.ModelViewSet):
    queryset = Manuscripts.objects.all().order_by('name')
    serializer_class = ManuscriptsSerializer

    filter_backends = [DatatablesFilterBackend]


    def get_queryset(self):
        # Extract ordering parameters from DataTables formatted request


        order_column_name = self.request.query_params.get('order_column', 'main_script')
        #print('order_column_name:'+str(order_column_name))
        order_direction = self.request.query_params.get('order_direction', 'dsc')
        #print('order_direction:'+str(order_direction))

        name = self.request.query_params.get('name')
        foreign_id = self.request.query_params.get('foreign_id')
        liturgical_genre = self.request.query_params.get('liturgical_genre')
        contemporary_repository_place = self.request.query_params.get('contemporary_repository_place')
        shelfmark = self.request.query_params.get('shelfmark')
        dating = self.request.query_params.get('dating')
        place_of_origin = self.request.query_params.get('place_of_origin')
        main_script = self.request.query_params.get('main_script')
        binding_date = self.request.query_params.get('binding_date')

        # Pobierz wartości zapytań dla minimalnych i maksymalnych wartości
        #how_many_columns_min = self.request.query_params.get('how_many_columns_min')
        #how_many_columns_max = self.request.query_params.get('how_many_columns_max')
        how_many_columns = self.request.query_params.get('how_many_columns')
        
        lines_per_page_min = self.request.query_params.get('lines_per_page_min')
        lines_per_page_max = self.request.query_params.get('lines_per_page_max')
        how_many_quires_min = self.request.query_params.get('how_many_quires_min')
        how_many_quires_max = self.request.query_params.get('how_many_quires_max')

        # Filtering for dating_min and dating_max
        dating_min = self.request.query_params.get('dating_min')
        dating_max = self.request.query_params.get('dating_max')
        dating_years_min = self.request.query_params.get('dating_years_min')
        dating_years_max = self.request.query_params.get('dating_years_max')

        clla_dating_min = self.request.query_params.get('clla_dating_min')
        clla_dating_max = self.request.query_params.get('clla_dating_max')
        clla_dating_years_min = self.request.query_params.get('clla_dating_years_min')
        clla_dating_years_max = self.request.query_params.get('clla_dating_years_max')

        binding_date_min = self.request.query_params.get('binding_date_min')
        binding_date_max = self.request.query_params.get('binding_date_max')
        binding_date_years_min = self.request.query_params.get('binding_date_years_min')
        binding_date_years_max = self.request.query_params.get('binding_date_years_max')


        decoration_true = self.request.query_params.get('decoration_true')
        decoration_false = self.request.query_params.get('decoration_false')
        decoration_true = True if decoration_true == "true" else False if decoration_true == "false" else None
        decoration_false = True if decoration_false == "true" else False if decoration_false == "false" else None
        
        
        music_notation_true = self.request.query_params.get('music_notation_true')
        music_notation_false = self.request.query_params.get('music_notation_false')
        music_notation_true = True if music_notation_true == "true" else False if music_notation_true == "false" else None
        music_notation_false = True if music_notation_false == "true" else False if music_notation_false == "false" else None

        
        digitized_true = self.request.query_params.get('digitized_true')
        digitized_false = self.request.query_params.get('digitized_false')
        digitized_true = True if digitized_true == "true" else False if digitized_true == "false" else None
        digitized_false = True if digitized_false == "true" else False if digitized_false == "false" else None

        musicology_original_true = self.request.query_params.get('musicology_original_true')
        musicology_original_false = self.request.query_params.get('musicology_original_false')
        musicology_on_lines_true = self.request.query_params.get('musicology_on_lines_true')
        musicology_on_lines_false = self.request.query_params.get('musicology_on_lines_false')
        musicology_original_true = True if musicology_original_true == "true" else False if musicology_original_true == "false" else None
        musicology_original_false = True if musicology_original_false == "true" else False if musicology_original_false == "false" else None
        musicology_on_lines_true = True if musicology_on_lines_true == "true" else False if musicology_on_lines_true == "false" else None
        musicology_on_lines_false = True if musicology_on_lines_false == "true" else False if musicology_on_lines_false == "false" else None

        projectId = int(self.request.query_params.get('projectId'))

        #text values
        formula_text = self.request.query_params.get('formula_text')
        rubric_name_from_ms = self.request.query_params.get('rubric_name_from_ms')
        clla_no = self.request.query_params.get('clla_no')


        queryset = Manuscripts.objects.all()

        #print("projectId = "+str(projectId))
        if projectId != 0:
            queryset = queryset.filter(ms_projects__project__id=projectId)

        #Always only main
        queryset = queryset.filter(display_as_main=True)

        
        #Main search
        search_value = self.request.GET.get('search[value]', None)

        #print("search_value "+search_value)

        

        if search_value:
            # Assuming you want to search in 'name', 'author', and 'description' fields
            queryset = queryset.filter(
                Q(name__icontains=search_value) |
                Q(rism_id__icontains=search_value) |
                Q(foreign_id__icontains=search_value) |
                Q(shelf_mark__icontains=search_value) |
                Q(common_name__icontains=search_value) |

                Q(contemporary_repository_place__country_today_eng__icontains=search_value) |
                Q(contemporary_repository_place__region_today_eng__icontains=search_value) |
                Q(contemporary_repository_place__city_today_eng__icontains=search_value) |
                Q(contemporary_repository_place__repository_today_eng__icontains=search_value) |

                Q(place_of_origin__country_today_eng__icontains=search_value) |
                Q(place_of_origin__region_today_eng__icontains=search_value) |
                Q(place_of_origin__city_today_eng__icontains=search_value) |
                Q(place_of_origin__repository_today_eng__icontains=search_value) |

                Q(dating__time_description__icontains=search_value) |

                Q(general_comment__icontains=search_value) |

                Q(main_script__name__icontains=search_value)

                #Q(contemporary_repository_place__icontains=search_value)
            )

                
                    
        # Apply the filter for name if provided
        if name:
            name_ids = name.split(';')  # Rozdziel wartość name na listę identyfikatorów
            queryset = queryset.filter(id__in=name_ids)  # Przefiltruj wyniki, aby pasowały do identyfikatorów z listy
        if foreign_id:
            queryset = queryset.filter(foreign_id=foreign_id)
        if liturgical_genre:
            queryset = queryset.filter(ms_genres__genre__id=liturgical_genre)
        if contemporary_repository_place:
            contemporary_repository_place_ids = contemporary_repository_place.split(';')
            queryset = queryset.filter(contemporary_repository_place__in=contemporary_repository_place_ids)
        if shelfmark:
            shelfmark_ids = shelfmark.split(';')
            queryset = queryset.filter(shelf_mark__in=shelfmark_ids)
        if dating:
            dating_ids = dating.split(';')
            queryset = queryset.filter(dating__in=dating_ids)
        if place_of_origin:
            place_of_origin_ids = place_of_origin.split(';')
            queryset = queryset.filter(place_of_origin__in=place_of_origin_ids)
        if main_script:
            main_script_ids = main_script.split(';')
            queryset = queryset.filter(main_script__in=main_script_ids)
        if binding_date:
            binding_date_ids = binding_date.split(';')
            queryset = queryset.filter(binding_date__in=binding_date_ids)
        if how_many_columns:
            how_many_columns_ids = how_many_columns.split(';')
            queryset = queryset.filter(how_many_columns_mostly__in=how_many_columns_ids)
        


        # Filtruj po minimalnych wartościach, jeśli są dostarczone
        #if how_many_columns_min and how_many_columns_min.isdigit():
        #    queryset = queryset.filter(how_many_columns_mostly__gte=int(how_many_columns_min))
        if lines_per_page_min and lines_per_page_min.isdigit():
            queryset = queryset.filter(lines_per_page_usually__gte=int(lines_per_page_min))
        if how_many_quires_min and how_many_quires_min.isdigit():
            queryset = queryset.filter(how_many_quires__gte=int(how_many_quires_min))

        # Filtruj po maksymalnych wartościach, jeśli są dostarczone
        #if how_many_columns_max and how_many_columns_max.isdigit():
        #    queryset = queryset.filter(how_many_columns_mostly__lte=int(how_many_columns_max))
        if lines_per_page_max and lines_per_page_max.isdigit():
            queryset = queryset.filter(lines_per_page_usually__lte=int(lines_per_page_max))
        if how_many_quires_max and how_many_quires_max.isdigit():
            queryset = queryset.filter(how_many_quires__lte=int(how_many_quires_max))

        if binding_date_min and binding_date_min.isdigit():
            queryset = queryset.filter(Q(binding_date__century_from__gte=int(binding_date_min)) | Q(binding_date__century_to__gte=int(binding_date_min)))

        if binding_date_max and binding_date_max.isdigit():
            queryset = queryset.filter(Q(binding_date__century_from__lte=int(binding_date_max)) | Q(binding_date__century_to__lte=int(binding_date_max)))
        
        if binding_date_years_min and binding_date_years_min.isdigit():
            queryset = queryset.filter(Q(binding_date__year_from__gte=int(binding_date_years_min)) | Q(binding_date__year_to__gte=int(binding_date_years_min)))

        if binding_date_years_max and binding_date_years_max.isdigit():
            queryset = queryset.filter(Q(binding_date__year_from__lte=int(binding_date_years_max)) | Q(binding_date__year_to__lte=int(binding_date_years_max)))

        if dating_min and dating_min.isdigit():
            queryset = queryset.filter(Q(dating__century_from__gte=int(dating_min)) | Q(dating__century_to__gte=int(dating_min)))

        if dating_max and dating_max.isdigit():
            queryset = queryset.filter(Q(dating__century_from__lte=int(dating_max)) | Q(dating__century_to__lte=int(dating_max)))

        if dating_years_min and dating_years_min.isdigit():
            queryset = queryset.filter(Q(dating__year_from__gte=int(dating_years_min)) | Q(dating__year_to__gte=int(dating_years_min)))

        if dating_years_max and dating_years_max.isdigit():
            queryset = queryset.filter(Q(dating__year_from__lte=int(dating_years_max)) | Q(dating__year_to__lte=int(dating_years_max)))



        if clla_dating_min and clla_dating_min.isdigit():
            queryset = queryset.filter(Q(ms_clla__dating__century_from__gte=int(clla_dating_min)) | Q(ms_clla__dating__century_to__gte=int(clla_dating_min)))

        if clla_dating_max and clla_dating_max.isdigit():
            queryset = queryset.filter(Q(ms_clla__dating__century_from__lte=int(clla_dating_max)) | Q(ms_clla__dating__century_to__lte=int(clla_dating_max)))

        if clla_dating_years_min and clla_dating_years_min.isdigit():
            queryset = queryset.filter(Q(ms_clla__dating__year_from__gte=int(clla_dating_years_min)) | Q(ms_clla__dating__year_to__gte=int(clla_dating_years_min)))

        if clla_dating_years_max and clla_dating_years_max.isdigit():
            queryset = queryset.filter(Q(ms_clla__dating__year_from__lte=int(clla_dating_years_max)) | Q(ms_clla__dating__year_to__lte=int(clla_dating_years_max)))


        if decoration_false and not decoration_true:
            queryset = queryset.filter(decorated=False)
        if decoration_true and not decoration_false:
            queryset = queryset.filter(decorated=True)

        if music_notation_false and not music_notation_true:
            queryset = queryset.filter(music_notation=False)
        if music_notation_true and not music_notation_false:
            queryset = queryset.filter(music_notation=True)

        if digitized_false and not digitized_true:
            queryset = queryset.filter(Q(iiif_manifest_url__isnull=True) | Q(iiif_manifest_url__exact=''), Q(links__isnull=True) | Q(links__exact=''))
        if digitized_true and not digitized_false:
            queryset = queryset.filter(Q(iiif_manifest_url__isnull=False) & ~Q(iiif_manifest_url__exact='') | Q(links__isnull=False) & ~Q(links__exact=''))

        if musicology_original_true and not musicology_original_false:
            queryset =queryset.filter(ms_music_notation__original=True)
        if musicology_original_false and not musicology_original_true:
            queryset =queryset.filter(ms_music_notation__original=False)
        if musicology_on_lines_true and not musicology_on_lines_false:
            queryset =queryset.filter(ms_music_notation__on_lines=True)
        if musicology_on_lines_false and not musicology_on_lines_true: 
            queryset =queryset.filter(ms_music_notation__on_lines=False)

        #NEW CHECKS:
        foliation = self.request.query_params.get('foliation')
        pagination = self.request.query_params.get('pagination')
        foliation = True if foliation == "true" else False if foliation == "false" else None
        pagination = True if pagination == "true" else False if pagination == "false" else None
        if foliation and not pagination:
            queryset = queryset.filter(foliation_or_pagination="FOLIATION")
        if pagination and not foliation:
            queryset = queryset.filter(foliation_or_pagination="PAGINATION")

        number_of_parchment_folios_min = self.request.query_params.get('number_of_parchment_folios_min')
        number_of_parchment_folios_max = self.request.query_params.get('number_of_parchment_folios_max')
        # Check if number_of_parchment_folios_min is provided and is a digit
        if number_of_parchment_folios_min and number_of_parchment_folios_min.isdigit():
            queryset = queryset.filter(ms_codicology__number_of_parchment_folios__gte=int(number_of_parchment_folios_min))

        # Check if number_of_parchment_folios_max is provided and is a digit
        if number_of_parchment_folios_max and number_of_parchment_folios_max.isdigit():
            queryset = queryset.filter(ms_codicology__number_of_parchment_folios__lte=int(number_of_parchment_folios_max))


        #New true/false values:
        paper_leafs_true = self.request.query_params.get('paper_leafs_true')
        watermarks_true = self.request.query_params.get('watermarks_true')
        is_main_text_true = self.request.query_params.get('is_main_text_true')
        is_hand_identified_true = self.request.query_params.get('is_hand_identified_true')
        written_above_the_top_line_true = self.request.query_params.get('written_above_the_top_line_true')
        binding_decoration_true = self.request.query_params.get('binding_decoration_true')
        parchment_shrinkage_true = self.request.query_params.get('parchment_shrinkage_true')
        illegible_text_true = self.request.query_params.get('illegible_text_true')
        ink_corrosion_true = self.request.query_params.get('ink_corrosion_true')
        copper_corrosion_true = self.request.query_params.get('copper_corrosion_true')
        powdering_or_cracking_paint_layer_true = self.request.query_params.get('powdering_or_cracking_paint_layer_true')
        conservation_true = self.request.query_params.get('conservation_true')
        darkening_true = self.request.query_params.get('darkening_true')
        water_staining_true = self.request.query_params.get('water_staining_true')
        historic_repairs_true = self.request.query_params.get('historic_repairs_true')
        display_as_main_true = self.request.query_params.get('display_as_main_true')
        
        paper_leafs_false = self.request.query_params.get('paper_leafs_false')
        watermarks_false = self.request.query_params.get('watermarks_false')
        is_main_text_false = self.request.query_params.get('is_main_text_false')
        is_hand_identified_false = self.request.query_params.get('is_hand_identified_false')
        written_above_the_top_line_false = self.request.query_params.get('written_above_the_top_line_false')
        binding_decoration_false = self.request.query_params.get('binding_decoration_false')
        parchment_shrinkage_false = self.request.query_params.get('parchment_shrinkage_false')
        illegible_text_false = self.request.query_params.get('illegible_text_false')
        ink_corrosion_false = self.request.query_params.get('ink_corrosion_false')
        copper_corrosion_false = self.request.query_params.get('copper_corrosion_false')
        powdering_or_cracking_paint_layer_false = self.request.query_params.get('powdering_or_cracking_paint_layer_false')
        conservation_false = self.request.query_params.get('conservation_false')
        darkening_false = self.request.query_params.get('darkening_false')
        water_staining_false = self.request.query_params.get('water_staining_false')
        historic_repairs_false = self.request.query_params.get('historic_repairs_false')
        display_as_main_false = self.request.query_params.get('display_as_main_false')
        
        paper_leafs_true = True if paper_leafs_true == 'true' else False if paper_leafs_true == 'false' else None
        watermarks_true = True if watermarks_true == 'true' else False if watermarks_true == 'false' else None
        is_main_text_true = True if is_main_text_true == 'true' else False if is_main_text_true == 'false' else None
        is_hand_identified_true = True if is_hand_identified_true == 'true' else False if is_hand_identified_true == 'false' else None
        written_above_the_top_line_true = True if written_above_the_top_line_true == 'true' else False if written_above_the_top_line_true == 'false' else None
        binding_decoration_true = True if binding_decoration_true == 'true' else False if binding_decoration_true == 'false' else None
        parchment_shrinkage_true = True if parchment_shrinkage_true == 'true' else False if parchment_shrinkage_true == 'false' else None
        illegible_text_true = True if illegible_text_true == 'true' else False if binding_decoration_true == 'false' else None
        ink_corrosion_true = True if ink_corrosion_true == 'true' else False if ink_corrosion_true == 'false' else None
        copper_corrosion_true = True if copper_corrosion_true == 'true' else False if copper_corrosion_true == 'false' else None
        powdering_or_cracking_paint_layer_true = True if powdering_or_cracking_paint_layer_true == 'true' else False if powdering_or_cracking_paint_layer_true == 'false' else None
        conservation_true = True if conservation_true == 'true' else False if conservation_true == 'false' else None
        display_as_main_true = True if display_as_main_true == 'true' else False if display_as_main_true == 'false' else None
        
        paper_leafs_false = True if paper_leafs_false == 'true' else False if paper_leafs_false == 'false' else None
        watermarks_false = True if watermarks_false == 'true' else False if watermarks_false == 'false' else None
        is_main_text_false = True if is_main_text_false == 'true' else False if is_main_text_false == 'false' else None
        is_hand_identified_false = True if is_hand_identified_false == 'true' else False if is_hand_identified_false == 'false' else None
        written_above_the_top_line_false = True if written_above_the_top_line_false == 'true' else False if written_above_the_top_line_false == 'false' else None
        binding_decoration_false = True if binding_decoration_false == 'true' else False if binding_decoration_false == 'false' else None
        parchment_shrinkage_false = True if parchment_shrinkage_false == 'true' else False if parchment_shrinkage_false == 'false' else None
        illegible_text_false = True if illegible_text_false == 'true' else False if illegible_text_false == 'false' else None
        ink_corrosion_false = True if ink_corrosion_false == 'true' else False if ink_corrosion_false == 'false' else None
        copper_corrosion_false = True if copper_corrosion_false == 'true' else False if copper_corrosion_false == 'false' else None
        powdering_or_cracking_paint_layer_false = True if powdering_or_cracking_paint_layer_false == 'true' else False if powdering_or_cracking_paint_layer_false == 'false' else None
        conservation_false = True if conservation_false == 'true' else False if conservation_false == 'false' else None
        display_as_main_false = True if display_as_main_false == 'true' else False if display_as_main_false == 'false' else None

        darkening_true = True if darkening_true == 'true' else False if darkening_true == 'false' else None
        darkening_false = True if darkening_false == 'true' else False if darkening_false == 'false' else None
        water_staining_true = True if water_staining_true == 'true' else False if water_staining_true == 'false' else None
        water_staining_false = True if water_staining_false == 'true' else False if water_staining_false == 'false' else None
        historic_repairs_true = True if historic_repairs_true == 'true' else False if historic_repairs_true == 'false' else None
        historic_repairs_false = True if historic_repairs_false == 'true' else False if historic_repairs_false == 'false' else None


        if paper_leafs_false and not paper_leafs_true:
            queryset = queryset.exclude(ms_codicology__number_of_paper_leaves__gt=0)
        if paper_leafs_true and not paper_leafs_false:
            queryset = queryset.filter(ms_codicology__number_of_paper_leaves__gt=0)
            
        if watermarks_false and not watermarks_true:
            queryset = queryset.filter(ms_codicology__watermarks=False)
        if watermarks_true and not watermarks_false:
            queryset = queryset.filter(ms_codicology__watermarks=True)

        if is_main_text_false and not is_main_text_true:
            queryset = queryset.filter(ms_hands__is_main_text=False)
        if is_main_text_true and not is_main_text_false:
            queryset = queryset.exclude(ms_hands__is_main_text=False)

        if is_hand_identified_false and not is_hand_identified_true:
            queryset = queryset.annotate(has_identified_hands=Count('ms_hands', filter=Q(ms_hands__hand__is_identified=True))) \
                            .filter(has_identified_hands=0)  # Manuscripts with no identified hands

        if is_hand_identified_true and not is_hand_identified_false:
            queryset = queryset.filter(ms_hands__hand__is_identified=True).distinct()  # Manuscripts with at least one identified hand

        if written_above_the_top_line_false and not written_above_the_top_line_true:
            queryset = queryset.filter(ms_layouts__written_above_the_top_line=False)
        if written_above_the_top_line_true and not written_above_the_top_line_false:
            queryset = queryset.filter(ms_layouts__written_above_the_top_line=True)

        if binding_decoration_false and not binding_decoration_true:
            queryset = queryset.exclude(ms_binding_decorations__isnull=False)
        if binding_decoration_true and not binding_decoration_false:
            queryset = queryset.filter(ms_binding_decorations__isnull=False)

        if parchment_shrinkage_false and not parchment_shrinkage_true:
            queryset = queryset.filter(ms_condition__parchment_shrinkage=False)
        if parchment_shrinkage_true and not parchment_shrinkage_false:
            queryset = queryset.filter(ms_condition__parchment_shrinkage=True)
        
        if illegible_text_false and not illegible_text_true:
            queryset = queryset.filter(ms_condition__illegible_text=False)
        if illegible_text_true and not illegible_text_false:
            queryset = queryset.filter(ms_condition__illegible_text=True)
        
        if ink_corrosion_false and not ink_corrosion_true:
            queryset = queryset.filter(ms_condition__ink_corrosion=False)
        if ink_corrosion_true and not ink_corrosion_false:
            queryset = queryset.filter(ms_condition__ink_corrosion=True)
        
        if copper_corrosion_false and not copper_corrosion_true:
            queryset = queryset.filter(ms_condition__copper_corrosion=False)
        if copper_corrosion_true and not copper_corrosion_false:
            queryset = queryset.filter(ms_condition__copper_corrosion=True)

        if powdering_or_cracking_paint_layer_false and not powdering_or_cracking_paint_layer_true:
            queryset = queryset.filter(ms_condition__powdering_or_cracking_paint_layer=False)
        if powdering_or_cracking_paint_layer_true and not powdering_or_cracking_paint_layer_false:
            queryset = queryset.filter(ms_condition__powdering_or_cracking_paint_layer=True)

        if conservation_false and not conservation_true:
            queryset = queryset.filter(ms_condition__conservation=False)
        if conservation_true and not conservation_false:
            queryset = queryset.filter(ms_condition__conservation=True)

        if darkening_false and not darkening_true:
            queryset = queryset.filter(ms_condition__darkening=False)
        if darkening_true and not darkening_false:
            queryset = queryset.filter(ms_condition__darkening=True)

        if water_staining_false and not water_staining_true:
            queryset = queryset.filter(ms_condition__water_staining=False)
        if water_staining_true and not water_staining_false:
            queryset = queryset.filter(ms_condition__water_staining=True)

        if historic_repairs_false and not historic_repairs_true:
            queryset = queryset.filter(ms_condition__historic_repairs=False)
        if historic_repairs_true and not historic_repairs_false:
            queryset = queryset.filter(ms_condition__historic_repairs=True)

        #if display_as_main_false and not display_as_main_true:
        #    queryset = queryset.exclude(display_as_main=True)
        #if display_as_main_true and not display_as_main_false:
        #    queryset = queryset.filter(display_as_main=True)

        

        #New min/max values:
        binding_height_min = self.request.query_params.get('binding_height_min')
        binding_width_min = self.request.query_params.get('binding_width_min')
        written_space_height_min = self.request.query_params.get('written_space_height_min')
        written_space_width_min = self.request.query_params.get('written_space_width_min')
        distance_between_horizontal_ruling_min = self.request.query_params.get('distance_between_horizontal_ruling_min')
        distance_between_vertical_ruling_min = self.request.query_params.get('distance_between_vertical_ruling_min')
        ms_how_many_hands_min = self.request.query_params.get('ms_how_many_hands_min')
        page_size_w_min = self.request.query_params.get('page_size_w_min')
        page_size_h_min = self.request.query_params.get('page_size_h_min')
        parchment_thickness_min = self.request.query_params.get('parchment_thickness_min')
        binding_height_max = self.request.query_params.get('binding_height_max')
        binding_width_max = self.request.query_params.get('binding_width_max')
        written_space_height_max = self.request.query_params.get('written_space_height_max')
        written_space_width_max = self.request.query_params.get('written_space_width_max')
        distance_between_horizontal_ruling_max = self.request.query_params.get('distance_between_horizontal_ruling_max')
        distance_between_vertical_ruling_max = self.request.query_params.get('distance_between_vertical_ruling_max')
        ms_how_many_hands_max = self.request.query_params.get('ms_how_many_hands_max')
        page_size_w_max = self.request.query_params.get('page_size_w_max')
        page_size_h_max = self.request.query_params.get('page_size_h_max')
        parchment_thickness_max = self.request.query_params.get('parchment_thickness_max')
        block_size_min = self.request.query_params.get('block_size_min')
        block_size_max = self.request.query_params.get('block_size_max')

        if binding_height_min and binding_height_min.isdigit():
            queryset = queryset.filter(ms_binding__max_height__gte=int(binding_height_min))
        if binding_height_max and binding_height_max.isdigit():
            queryset = queryset.filter(ms_binding__max_height__lte=int(binding_height_max))

        if binding_width_min and binding_width_min.isdigit():
            queryset = queryset.filter(ms_binding__max_width__gte=int(binding_width_min))
        if binding_width_max and binding_width_max.isdigit():
            queryset = queryset.filter(ms_binding__max_width__lte=int(binding_width_max))

        if written_space_height_min and written_space_height_min.isdigit():
            queryset = queryset.filter(ms_layouts__written_space_height_max__gte=int(written_space_height_min))
        if written_space_height_max and written_space_height_max.isdigit():
            queryset = queryset.filter(ms_layouts__written_space_height_max__lte=int(written_space_height_max))

        if written_space_width_min and written_space_width_min.isdigit():
            queryset = queryset.filter(ms_layouts__written_space_width_max__gte=int(written_space_width_min))
        if written_space_width_max and written_space_width_max.isdigit():
            queryset = queryset.filter(ms_layouts__written_space_width_max__lte=int(written_space_width_max))
            
        if distance_between_horizontal_ruling_min and distance_between_horizontal_ruling_min.isdigit():
            queryset = queryset.filter(ms_layouts__distance_between_horizontal_ruling__gte=int(distance_between_horizontal_ruling_min))
        if distance_between_horizontal_ruling_max and distance_between_horizontal_ruling_max.isdigit():
            queryset = queryset.filter(ms_layouts__distance_between_horizontal_ruling__lte=int(distance_between_horizontal_ruling_max))

        if distance_between_vertical_ruling_min and distance_between_vertical_ruling_min.isdigit():
            queryset = queryset.filter(ms_layouts__distance_between_vertical_ruling__gte=int(distance_between_vertical_ruling_min))
        if distance_between_vertical_ruling_max and distance_between_vertical_ruling_max.isdigit():
            queryset = queryset.filter(ms_layouts__distance_between_vertical_ruling__lte=int(distance_between_vertical_ruling_max))

        if ms_how_many_hands_min and ms_how_many_hands_min.isdigit():
            queryset = queryset.annotate(num_hands=Count('ms_hands', filter=Q(ms_hands__is_main_text=True))) \
                            .filter(num_hands__gte=int(ms_how_many_hands_min))
        if ms_how_many_hands_max and ms_how_many_hands_max.isdigit():
            queryset = queryset.annotate(num_hands=Count('ms_hands', filter=Q(ms_hands__is_main_text=True))) \
                            .filter(num_hands__lte=int(ms_how_many_hands_max))

        if page_size_w_min and page_size_w_min.isdigit():
            queryset = queryset.filter(
                Q(ms_codicology__page_size_max_width__gte=int(page_size_w_min))
            )

        if page_size_w_max and page_size_w_max.isdigit():
            queryset = queryset.filter(
                Q(ms_codicology__page_size_max_width__lte=int(page_size_w_max))
            )

        if page_size_h_min and page_size_h_min.isdigit():
            queryset = queryset.filter(
                Q(ms_codicology__page_size_max_height__gte=int(page_size_h_min))
            )

        if page_size_h_max and page_size_h_max.isdigit():
            queryset = queryset.filter(
                Q(ms_codicology__page_size_max_height__lte=int(page_size_h_max))
            )


        if parchment_thickness_min and float(parchment_thickness_min):
            queryset = queryset.filter(ms_codicology__parchment_thickness_min__gte=float(parchment_thickness_min))
        if parchment_thickness_max and float(parchment_thickness_max):
            queryset = queryset.filter(ms_codicology__parchment_thickness_max__lte=float(parchment_thickness_max))

        if block_size_min and block_size_min.isdigit():
            queryset = queryset.filter(ms_binding__block_max__gte=int(block_size_min))
        if block_size_max and block_size_max.isdigit():
            queryset = queryset.filter(ms_binding__block_max__lte=int(block_size_max))

        
        #Decoration min/max:
        decoration_size_height_min = self.request.query_params.get('decoration_size_height_min')
        decoration_size_height_max = self.request.query_params.get('decoration_size_height_max')
        decoration_size_width_min = self.request.query_params.get('decoration_size_width_min')
        decoration_size_width_max = self.request.query_params.get('decoration_size_width_max')
        decoration_addition_date_min = self.request.query_params.get('decoration_addition_date_min')
        decoration_addition_date_max = self.request.query_params.get('decoration_addition_date_max')
        decoration_addition_date_years_min = self.request.query_params.get('decoration_addition_date_years_min')
        decoration_addition_date_years_max = self.request.query_params.get('decoration_addition_date_years_max')
        musicology_how_many_lines_min = self.request.query_params.get('musicology_how_many_lines_min')
        musicology_how_many_lines_max = self.request.query_params.get('musicology_how_many_lines_max')

        if decoration_size_height_min and decoration_size_height_min.isdigit():
            queryset = queryset.filter(ms_decorations__size_height_min__gte=int(decoration_size_height_min))
        if decoration_size_height_max and decoration_size_height_max.isdigit():
            queryset = queryset.filter(ms_decorations__size_height_max__lte=int(decoration_size_height_max))

        if decoration_size_width_min and decoration_size_width_min.isdigit():
            queryset = queryset.filter(ms_decorations__size_width_min__gte=int(decoration_size_width_min))
        if decoration_size_width_max and decoration_size_width_max.isdigit():
            queryset = queryset.filter(ms_decorations__size_width_max__lte=int(decoration_size_width_max))

        if decoration_addition_date_min and decoration_addition_date_min.isdigit():
            queryset = queryset.filter(ms_decorations__date_of_the_addition__century_from__gte=int(decoration_addition_date_min))
        if decoration_addition_date_max and decoration_addition_date_max.isdigit():
            queryset = queryset.filter(ms_decorations__date_of_the_addition__century_from__lte=int(decoration_addition_date_max))

        if decoration_addition_date_years_min and decoration_addition_date_years_min.isdigit():
            queryset = queryset.filter(ms_decorations__date_of_the_addition__year_from__gte=int(decoration_addition_date_years_min))
        if decoration_addition_date_years_max and decoration_addition_date_years_max.isdigit():
            queryset = queryset.filter(ms_decorations__date_of_the_addition__year_to__lte=int(decoration_addition_date_years_max))


        if musicology_how_many_lines_min and musicology_how_many_lines_min.isdigit():
            queryset = queryset.filter(ms_music_notation__number_of_lines__gte=int(musicology_how_many_lines_min))
        if musicology_how_many_lines_max and musicology_how_many_lines_max.isdigit():
            queryset = queryset.filter(ms_music_notation__number_of_lines__lte=int(musicology_how_many_lines_max))

        #New select values:
        parchment_colour_select = self.request.query_params.get('parchment_colour_select')
        main_script_select = self.request.query_params.get('main_script_select')
        type_of_the_quire_select = self.request.query_params.get('type_of_the_quire_select')
        script_name_select = self.request.query_params.get('script_name_select')
        ruling_method_select = self.request.query_params.get('ruling_method_select')
        pricking_select = self.request.query_params.get('pricking_select')
        binding_place_of_origin_select = self.request.query_params.get('binding_place_of_origin_select')
        binding_type_select = self.request.query_params.get('binding_type_select')
        binding_style_select = self.request.query_params.get('binding_style_select')
        binding_material_select = self.request.query_params.get('binding_material_select')
        binding_components_select = self.request.query_params.get('binding_components_select')
        binding_category_select = self.request.query_params.get('binding_category_select')
        binding_decoration_type_select = self.request.query_params.get('binding_decoration_select')
        formula_select = self.request.query_params.get('formula_select')
        rubric_select = self.request.query_params.get('rubric_select')
        damage_select = self.request.query_params.get('damage_select')
        provenance_place_select = self.request.query_params.get('provenance_place_select')
        provenance_place_countries_select = self.request.query_params.get('provenance_place_countries_select')
        form_of_an_item_select = self.request.query_params.get('form_of_an_item_select')
        title_select = self.request.query_params.get('title_select')
        author_select = self.request.query_params.get('author_select')

        #New decotation:
        original_or_added_select = self.request.query_params.get('original_or_added_select')
        location_on_the_page_select = self.request.query_params.get('location_on_the_page_select')
        decoration_type_select = self.request.query_params.get('decoration_type_select')
        decoration_subtype_select = self.request.query_params.get('decoration_subtype_select')
        size_characteristic_select = self.request.query_params.get('size_characteristic_select')
        monochrome_or_colour_select = self.request.query_params.get('monochrome_or_colour_select')
        technique_select = self.request.query_params.get('technique_select')
        ornamented_text_select = self.request.query_params.get('ornamented_text_select')
        decoration_subject_select = self.request.query_params.get('decoration_subject_select')
        decoration_colours_select = self.request.query_params.get('decoration_colours_select')
        decoration_characteristics_select = self.request.query_params.get('decoration_characteristics_select')
        musicology_type_select = self.request.query_params.get('musicology_type_select')

        clla_liturgical_genre_select = self.request.query_params.get('clla_liturgical_genre_select')
        clla_provenance_place_select = self.request.query_params.get('clla_provenance_place_select')

        if parchment_colour_select: 
            parchment_colour_select_ids = parchment_colour_select.split(';')
            queryset = queryset.filter(ms_codicology__parchment_colour__in=parchment_colour_select_ids)
        if main_script_select: 
            main_script_select_ids = main_script_select.split(';')
            queryset = queryset.filter(main_script__in=main_script_select_ids)
        if type_of_the_quire_select: 
            type_of_the_quire_select_ids = type_of_the_quire_select.split(';')
            for q in type_of_the_quire_select_ids:
                queryset = queryset.filter(ms_quires__type_of_the_quire=q)
        if script_name_select: 
            script_name_select_ids = script_name_select.split(';')
            for q in script_name_select_ids:
                queryset = queryset.filter(ms_hands__script_name=q)
        if ruling_method_select: 
            ruling_method_select_ids = ruling_method_select.split(';')
            for q in ruling_method_select_ids:
                queryset = queryset.filter(ms_layouts__ruling_method=q)
        if pricking_select: 
            pricking_select_ids = pricking_select.split(';')
            for q in pricking_select_ids:
                queryset = queryset.filter(ms_layouts__pricking=q)
        if binding_place_of_origin_select: 
            binding_place_of_origin_select_ids = binding_place_of_origin_select.split(';')
            queryset = queryset.filter(ms_binding__place_of_origin__in=binding_place_of_origin_select_ids)
        if binding_type_select: 
            binding_type_select_ids = binding_type_select.split(';')
            queryset = queryset.filter(ms_binding__type_of_binding__in=binding_type_select_ids)
        if binding_style_select: 
            binding_style_select_ids = binding_style_select.split(';')
            queryset = queryset.filter(ms_binding__style_of_binding__in=binding_style_select_ids)
        if binding_material_select: 
            binding_material_select_ids = binding_material_select.split(';')
            for q in binding_material_select_ids:
                queryset = queryset.filter(ms_binding_materials__material=q)
        if binding_components_select: 
            binding_components_select_ids = binding_components_select.split(';')
            for q in binding_components_select_ids:
                queryset = queryset.filter(ms_binding_components__component=q)
        if binding_category_select: 
            binding_category_select_ids = binding_category_select.split(';')
            for q in binding_category_select_ids:
                queryset = queryset.filter(ms_binding__category=q)
        if binding_decoration_type_select: 
            binding_decoration_type_select_ids = binding_decoration_type_select.split(';')
            for q in binding_decoration_type_select_ids:
                queryset = queryset.filter(ms_binding_decorations__decoration=q)
        if formula_select: 
            formula_select_ids = formula_select.split(';')
            for q in formula_select_ids:
                queryset = queryset.filter(ms_content__formula=q)
        if rubric_select: 
            rubric_select_ids = rubric_select.split(';')
            for q in rubric_select_ids:
                queryset = queryset.filter(ms_content__rubric=q)
        if damage_select: 
            damage_select_ids = damage_select.split(';')
            queryset = queryset.filter(ms_condition__damage__in=damage_select_ids)
        if provenance_place_select: 
            provenance_place_select_ids = provenance_place_select.split(';')
            for q in provenance_place_select_ids:
                queryset = queryset.filter(ms_provenance__place=q)
        if provenance_place_countries_select: 
            provenance_place_countries_select_ids = provenance_place_countries_select.split(';')
            for q in provenance_place_countries_select_ids:
                queryset = queryset.filter(ms_provenance__place__country_today_eng=q)
        if form_of_an_item_select: 
            form_of_an_item_select_ids = form_of_an_item_select.split(';')
            queryset = queryset.filter(form_of_an_item__in=form_of_an_item_select_ids)

        if title_select: 
            title_select_ids = title_select.split(';')
            for q in title_select_ids:
                queryset = queryset.filter(ms_bibliography__bibliography=q)
        if author_select: 
            author_select_ids = author_select.split(';')
            for q in author_select_ids:
                queryset = queryset.filter(ms_bibliography__bibliography__author=q)

        if clla_liturgical_genre_select: 
            clla_liturgical_genre_select_ids = clla_liturgical_genre_select.split(';')
            for q in clla_liturgical_genre_select_ids:
                queryset = queryset.filter(ms_clla__liturgical_genre=q)
        if clla_provenance_place_select: 
            clla_provenance_place_select_ids = clla_provenance_place_select.split(';')
            for q in clla_provenance_place_select_ids:
                queryset = queryset.filter(ms_clla__provenance=q)

        if original_or_added_select: 
            original_or_added_select_ids = original_or_added_select.split(';')
            #queryset = queryset.filter(ms_decorations__original_or_added__in=original_or_added_select_ids)
            for q in original_or_added_select_ids:
                queryset = queryset.filter(ms_decorations__original_or_added=q)
        if location_on_the_page_select: 
            location_on_the_page_select_ids = location_on_the_page_select.split(';')
            #queryset = queryset.filter(ms_decorations__location_on_the_page__in=location_on_the_page_select_ids)
            for q in location_on_the_page_select_ids:
                queryset = queryset.filter(ms_decorations__location_on_the_page=q)

        if decoration_type_select: 
            decoration_type_select_ids = decoration_type_select.split(';')
            #queryset = queryset.filter(ms_decorations__decoration_type__in=decoration_type_select_ids)
            for q in decoration_type_select_ids:
                queryset = queryset.filter(ms_decorations__decoration_type=q)
        if decoration_subtype_select: 
            decoration_subtype_select_ids = decoration_subtype_select.split(';')
            #queryset = queryset.filter(ms_decorations__decoration_subtype__in=decoration_subtype_select_ids)
            for q in decoration_subtype_select_ids:
                queryset = queryset.filter(ms_decorations__decoration_subtype=q)

        if size_characteristic_select: 
            size_characteristic_select_ids = size_characteristic_select.split(';')
            #queryset = queryset.filter(ms_decorations__size_characteristic__in=size_characteristic_select_ids)
            for q in size_characteristic_select_ids:
                queryset = queryset.filter(ms_decorations__size_characteristic=q)
        if monochrome_or_colour_select: 
            monochrome_or_colour_select_ids = monochrome_or_colour_select.split(';')
            #queryset = queryset.filter(ms_decorations__monochrome_or_colour__in=monochrome_or_colour_select_ids)
            for q in monochrome_or_colour_select_ids:
                queryset = queryset.filter(ms_decorations__monochrome_or_colour=q)
        if technique_select: 
            technique_select_ids = technique_select.split(';')
            #queryset = queryset.filter(ms_decorations__technique__in=technique_select_ids)
            for q in technique_select_ids:
                queryset = queryset.filter(ms_decorations__technique=q)
        if ornamented_text_select: 
            ornamented_text_select_ids = ornamented_text_select.split(';')
            #queryset = queryset.filter(ms_decorations__ornamented_text__in=ornamented_text_select_ids)
            for q in ornamented_text_select_ids:
                queryset = queryset.filter(ms_decorations__ornamented_text=q)
        if decoration_subject_select: 
            decoration_subject_select_ids = decoration_subject_select.split(';')
            #queryset = queryset.filter(ms_decorations__decoration_subjects__subject__in=decoration_subject_select_ids)
            for q in decoration_subject_select_ids:
                queryset = queryset.filter(ms_decorations__decoration_subjects__subject=q)
        if decoration_colours_select: 
            decoration_colours_select_ids = decoration_colours_select.split(';')
            #queryset = queryset.filter(ms_decorations__decoration_colours__colour__in=decoration_colours_select_ids)
            for q in decoration_colours_select_ids:
                queryset = queryset.filter(ms_decorations__decoration_colours__colour=q)
        if decoration_characteristics_select: 
            decoration_characteristics_select_ids = decoration_characteristics_select.split(';')
            #queryset = queryset.filter(ms_decorations__decoration_characteristics__characteristics__in=decoration_characteristics_select_ids)
            for q in decoration_characteristics_select_ids:
                queryset = queryset.filter(ms_decorations__decoration_characteristics__characteristics=q)

        if musicology_type_select: 
            musicology_type_select_ids = musicology_type_select.split(';')
            #queryset = queryset.filter(ms_decorations__decoration_characteristics__characteristics__in=musicology_type_select_ids)
            for q in musicology_type_select_ids:
                queryset = queryset.filter(ms_music_notation__music_notation_name=q)

        if formula_text and len(formula_text)>1:
            queryset = queryset.filter(ms_content__formula_text__icontains=formula_text)
        if rubric_name_from_ms and len(rubric_name_from_ms)>1:
            queryset = queryset.filter(ms_content__rubric_name_from_ms__icontains=rubric_name_from_ms)
        
        if clla_no and len(clla_no)>=1:
            queryset = queryset.filter(ms_clla__clla_no__icontains=clla_no)


    
        # Apply ordering to queryset
        if order_direction == 'asc':
            queryset = queryset.order_by(F(order_column_name).asc(nulls_last=True))
        else:
            queryset = queryset.order_by(F(order_column_name).desc(nulls_last=True))


        return queryset.distinct()

    

# class assistantAjaxView(LoginRequiredMixin,View):

#     def get(self, request, *args, **kwargs):
#         q = self.request.GET.get('q')
#         projectId = self.request.GET.get('project_id', None)
#         #print(q)
#         sql_text = self.text_to_sql(request,q,projectId)


#         #print(sql)
#         answer = self.sql_query(sql_text['sql'])
#         json_output = (answer)
#         #print(json_output)

#         data = {
#             'info': json_output,
#             'text': sql_text['text']
#         }

#         return JsonResponse(data)

#     def text_to_sql(self, request, text,projectId):
        
#         #return generate_sql(text, fast=False)

#         return gpt_generate_sql(request,text,projectId)


#     def sql_query(self,query):
#         with connection.cursor() as cursor:

#             try:
#                 cursor.execute(query)

#             except Exception as e:
#                 print(e)
#                 return None

            
#             try: 
#                 r = [dict((cursor.description[i][0], value) \
#                     for i, value in enumerate(row)) for row in cursor.fetchall()]
#                 return r

#             except TypeError as e:
#                 print(e)
#                 return None

#         return None


## Modified views.py fragment


class AssistantStartView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        q = request.GET.get('q')
        project_id = request.GET.get('project_id', 0)
        if not q:
            return JsonResponse({'error': 'No question provided'})
        ai_query = AIQuery.objects.create(
            user=request.user,
            project_id=project_id,
            question=q,
            status='pending'
        )
        threading.Thread(target=process_ai_query, args=(ai_query.id,)).start()
        return JsonResponse({'query_id': ai_query.id})

class AssistantStatusView(LoginRequiredMixin, View):
    def get(self, request, query_id, *args, **kwargs):
        try:
            ai_query = AIQuery.objects.get(id=query_id, user=request.user)
            conversation = json.loads(ai_query.conversation) if ai_query.conversation else []
            messages = [{'role': msg['role'], 'content': msg['content']} for msg in conversation if msg['role'] != 'system']
            data = {
                'status': ai_query.status,
                'messages': messages,
                'result': json.loads(ai_query.result) if ai_query.result else None,
                'error': ai_query.error,
                'execution_time': ai_query.execution_time
            }
            return JsonResponse(data)
        except AIQuery.DoesNotExist:
            return JsonResponse({'error': 'Query not found'}, status=404)

# Remove or comment out the old assistantAjaxView if not needed
# class assistantAjaxView(...)

class CodicologyAjaxView(View):
    def get(self, request, *args, **kwargs):
        pk = self.request.GET.get('pk')
        ms_instance = get_object_or_404(Manuscripts, id=pk)
        skip_fields = ['manuscript']  # Add any other fields to skip
        instance = ms_instance.ms_codicology.first()
        info = get_obj_dictionary(instance,skip_fields)

        debate = []
        if instance:
            debate_query = AttributeDebate.objects.filter(content_type__model='codicology', object_id=instance.id)
            for d in debate_query:
                bibliography = Bibliography.objects.get(id=d.bibliography_id)
                # Create a dictionary with debate details
                debate_dict = {
                    'id': d.id,
                    'field_name': d.field_name,
                    'text': d.text,
                    'bibliography': str(bibliography),  # String representation of the Bibliography name
                    'bibliography_id': d.bibliography_id 
                }
                
                # Append the dictionary to the debate_data list
                debate.append(debate_dict)

        # Create the response dictionary
        data = {
            'info': info,
            'debate': debate,  # Convert QuerySet to a list for JSON serialization
        }

        return JsonResponse(data)


class LayoutsAjaxView(View):
    def get(self, request, *args, **kwargs):
        pk = self.request.GET.get('ms')
        ms_instance = get_object_or_404(Manuscripts, id=pk)
        skip_fields = ['manuscript']  # Add any other fields to skip
        info_queryset = ms_instance.ms_layouts.all()
        info_dict = [get_obj_dictionary(entry, skip_fields) for entry in info_queryset]

        # Create the response dictionary
        data = {
            'data': info_dict,
        }

        return JsonResponse(data)

class DecorationAjaxView(View):
    def get(self, request, *args, **kwargs):
        pk = self.request.GET.get('ms')
        decoration_type = self.request.GET.get('decoration_type')

        ms_instance = get_object_or_404(Manuscripts, id=pk)
        skip_fields = ['manuscript']  # Add any other fields to skip
        info_queryset = ms_instance.ms_decorations.all()

        if decoration_type and len(decoration_type)>3 :
            info_queryset = info_queryset.filter(decoration_type__name=decoration_type)

        info_dict = []
        for entry in info_queryset:
            obj_dict = get_obj_dictionary(entry, skip_fields)
            
            # Fetching related subjects, colours, and characteristics
            obj_dict['decoration_subjects'] = [str(sub.subject) for sub in entry.decoration_subjects.all()]
            obj_dict['decoration_colours'] = [str(col.colour) for col in entry.decoration_colours.all()]
            obj_dict['decoration_characteristics'] = [str(char.characteristics) for char in entry.decoration_characteristics.all()]
            
            obj_dict['entry_date'] = entry.entry_date.strftime('%Y-%m-%d')  # format date as string

            #obj_dict['location_on_the_page'] = entry.get_location_on_the_page_display()
            #obj_dict['size_characteristic'] = entry.get_size_characteristic_display()
            obj_dict['location_on_the_page'] = entry.get_location_on_the_page_display() or entry.location_on_the_page
            obj_dict['size_characteristic'] = entry.get_size_characteristic_display() or entry.size_characteristic


            info_dict.append(obj_dict)


        debate = []
        for instance in info_queryset:
            debate_query = AttributeDebate.objects.filter(content_type__model='decoration', object_id=instance.id)
            for d in debate_query:
                bibliography = Bibliography.objects.get(id=d.bibliography_id)
                # Create a dictionary with debate details
                debate_dict = {
                    'id': d.id,
                    'instance_id': instance.id,
                    'field_name': d.field_name,
                    'text': d.text,
                    'bibliography': str(bibliography),  # String representation of the Bibliography name
                    'bibliography_id': d.bibliography_id 
                }
                
                # Append the dictionary to the debate_data list
                debate.append(debate_dict)

        # Create the response dictionary
        data = {
            'data': info_dict,
            'debate': debate,
        }

        return JsonResponse(data)

class QuiresAjaxView(View):
    def get(self, request, *args, **kwargs):
        pk = self.request.GET.get('ms')
        ms_instance = get_object_or_404(Manuscripts, id=pk)
        skip_fields = ['manuscript']  # Add any other fields to skip
        info_queryset = ms_instance.ms_quires.all()
        info_dict = [get_obj_dictionary(entry, skip_fields) for entry in info_queryset]

        # Create the response dictionary
        data = {
            'data': info_dict,
        }

        return JsonResponse(data)

class ConditionAjaxView(View):
    def get(self, request, *args, **kwargs):
        pk = self.request.GET.get('ms')
        ms_instance = get_object_or_404(Manuscripts, id=pk)
        skip_fields = [ 'manuscript']  # Add any other fields to skip
        info_queryset = ms_instance.ms_condition.all()
        info_dict = [get_obj_dictionary(entry, skip_fields) for entry in info_queryset]

        # Create the response dictionary
        data = {
            'data': info_dict,
        }

        return JsonResponse(data)

class CllaAjaxView(View):
    def get(self, request, *args, **kwargs):
        pk = self.request.GET.get('ms')
        ms_instance = get_object_or_404(Manuscripts, id=pk)
        skip_fields = ['id', 'manuscript']  # Add any other fields to skip
        info_queryset = ms_instance.ms_clla.all()
        info_dict = [get_obj_dictionary(entry, skip_fields) for entry in info_queryset]

        # Create the response dictionary
        data = {
            'data': info_dict,
        }

        return JsonResponse(data)

class OriginsAjaxView(View):
    def get(self, request, *args, **kwargs):
        pk = self.request.GET.get('ms')
        ms_instance = get_object_or_404(Manuscripts, id=pk)
        skip_fields = ['manuscript']  # Add any other fields to skip
        info_queryset = ms_instance.ms_origins.all()
        info_dict = [get_obj_dictionary(entry, skip_fields) for entry in info_queryset]

        debate = []
        for instance in info_queryset:
            debate_query = AttributeDebate.objects.filter(content_type__model='origins', object_id=instance.id)
            for d in debate_query:
                bibliography = Bibliography.objects.get(id=d.bibliography_id)
                # Create a dictionary with debate details
                debate_dict = {
                    'id': d.id,
                    'instance_id': instance.id,
                    'field_name': d.field_name,
                    'text': d.text,
                    'bibliography': str(bibliography),  # String representation of the Bibliography name
                    'bibliography_id': d.bibliography_id 
                }
                
                # Append the dictionary to the debate_data list
                debate.append(debate_dict)

        # Create the response dictionary
        data = {
            'data': info_dict,
            'debate': debate
        }

        return JsonResponse(data)

class BindingAjaxView(View):
    def get(self, request, *args, **kwargs):
        pk = self.request.GET.get('ms')
        ms_instance = get_object_or_404(Manuscripts, id=pk)
        skip_fields = [ 'manuscript']  # Add any other fields to skip
        info_queryset = ms_instance.ms_binding.all()
        info_dict = [get_obj_dictionary(entry, skip_fields) for entry in info_queryset]

        #Binding materials:
        pk = self.request.GET.get('ms')
        ms_instance = get_object_or_404(Manuscripts, id=pk)
        skip_fields = ['id', 'manuscript']  # Add any other fields to skip
        info_queryset = ms_instance.ms_binding_materials.all()
        materials_dict = [get_obj_dictionary(entry, skip_fields) for entry in info_queryset]

        materials_str = ""

        for m in materials_dict:
            materials_str += m['material'] +", "
        materials_str = materials_str[:-2]


        #Binding decorations:
        pk = self.request.GET.get('ms')
        ms_instance = get_object_or_404(Manuscripts, id=pk)
        skip_fields = ['id', 'manuscript']  # Add any other fields to skip
        info_queryset = ms_instance.ms_binding_decorations.all()
        decorations_dict = [get_obj_dictionary(entry, skip_fields) for entry in info_queryset]

        decorations_str = ""

        for m in decorations_dict:
            decorations_str += m['decoration'] +", "
        decorations_str = decorations_str[:-2]

        if len(decorations_str) < 2:
            decorations_str = "No" 


        #Binding components:
        components_queryset = ms_instance.ms_binding_components.all()
        components_dict = [get_obj_dictionary(entry, skip_fields) for entry in components_queryset]

        components_str = ""

        for m in components_dict:
            components_str += m['component'] +", "
        components_str = components_str[:-2]

        if len(components_str) < 2:
            components_str = "No" 

        data = {}

        if len(info_dict) > 0:
            info_dict[0]['materials'] = materials_str
            info_dict[0]['decorations'] = decorations_str
            info_dict[0]['components'] = components_str


            # Create the response dictionary
            data = {
                'info': info_dict[0]
            }

        return JsonResponse(data)


class MusicNotationAjaxView(View):
    def get(self, request, *args, **kwargs):
        pk = self.request.GET.get('ms')
        ms_instance = get_object_or_404(Manuscripts, id=pk)
        skip_fields = [ 'manuscript']  # Add any other fields to skip
        info_queryset = ms_instance.ms_music_notation.all()
        info_dict = [get_obj_dictionary(entry, skip_fields) for entry in info_queryset]

        # Create the response dictionary
        data = {
            'data': info_dict,
        }

        return JsonResponse(data)

class HandsAjaxView(View):
    def get(self, request, *args, **kwargs):
        pk = self.request.GET.get('ms')
        is_main_text = self.request.GET.get('is_main_text')


        ms_instance = get_object_or_404(Manuscripts, id=pk)
        skip_fields = [ 'manuscript']  # Add any other fields to skip
        info_queryset = ms_instance.ms_hands.all()

        if is_main_text=='true' :
            info_queryset = info_queryset.filter(is_main_text=True)
        elif is_main_text == 'false' :
            info_queryset = info_queryset.filter(is_main_text=False)

        info_dict = [get_obj_dictionary(entry, skip_fields) for entry in info_queryset]


        debate = []
        for instance in info_queryset:
            debate_query = AttributeDebate.objects.filter(content_type__model='manuscripthands', object_id=instance.id)
            for d in debate_query:
                bibliography = Bibliography.objects.get(id=d.bibliography_id)
                # Create a dictionary with debate details
                debate_dict = {
                    'id': d.id,
                    'instance_id': instance.id,
                    'field_name': d.field_name,
                    'text': d.text,
                    'bibliography': str(bibliography),  # String representation of the Bibliography name
                    'bibliography_id': d.bibliography_id 
                }
                
                # Append the dictionary to the debate_data list
                debate.append(debate_dict)

        # Create the response dictionary
        data = {
            'data': info_dict,
            'debate': debate
        }

        return JsonResponse(data)

class WatermarksAjaxView(View):
    def get(self, request, *args, **kwargs):
        pk = self.request.GET.get('ms')
        ms_instance = get_object_or_404(Manuscripts, id=pk)
        info_queryset = ms_instance.ms_watermarks.all()  # ManuscriptWatermarks objects
        
        # Create a list of dictionaries for ManuscriptWatermarks, keeping id
        skip_fields = ['manuscript', 'watermark']  # Skip ForeignKey fields
        info_dict = [get_obj_dictionary(entry, skip_fields) for entry in info_queryset]

        # Merge all Watermark fields into the ManuscriptWatermarks dictionary, excluding Watermark id
        for idx, entry in enumerate(info_queryset):
            watermark_dict = get_obj_dictionary(entry.watermark, skip_fields=['id'])  # Skip Watermark id
            info_dict[idx].update(watermark_dict)

        # Create the response dictionary
        data = {
            'data': info_dict
        }
        return JsonResponse(data)

class BibliographyAjaxView(View):
    def get(self, request, *args, **kwargs):
        pk = self.request.GET.get('ms')
        ms_instance = get_object_or_404(Manuscripts, id=pk)

        # Get ManuscriptBibliography objects
        bibliography = ms_instance.ms_bibliography.all()

        # Serialize ManuscriptBibliography with Bibliography fields
        info_dict = []
        skip_fields = ['manuscript', 'bibliography']  # Exclude foreign key objects
        for entry in bibliography:
            bib_dict = get_obj_dictionary(entry.bibliography, skip_fields=['zotero_id'])  # Get Bibliography fields
            bib_dict['id'] = entry.id  # Use ManuscriptBibliography id
            info_dict.append(bib_dict)

        # Create the response dictionary
        data = {
            'data': info_dict,
        }

        return JsonResponse(data)

class BibliographyExportView(View):
    def get(self, request, *args, **kwargs):
        pk = self.request.GET.get('ms')
        ms_instance = get_object_or_404(Manuscripts, id=pk)

        #Zotero:
        bibliography = ms_instance.ms_bibliography.all()

        zot = zotero.Zotero(ZOTERO_library_id, ZOTERO_library_type, ZOTERO_api_key)
        zot.add_parameters(format='bibtex')
        #allItems = zot.items()

        info_str = ""
        for b in bibliography:
            item = zot.item(b.bibliography.zotero_id, limit=50, content='bibtex')
            info_str += item[0] + "\n\n"

        response = HttpResponse(info_str, content_type='application/x-bibtex charset=utf-8')
        return response

class BibliographyPrintView(View):
    def get(self, request, *args, **kwargs):
        pk = self.request.GET.get('ms')
        ms_instance = get_object_or_404(Manuscripts, id=pk)

        #Zotero:
        bibliography = ms_instance.ms_bibliography.all()

        zot = zotero.Zotero(ZOTERO_library_id, ZOTERO_library_type, ZOTERO_api_key)
        zot.add_parameters(format='bib')
        #allItems = zot.items()

        info_str = ""
        for b in bibliography:
            item = zot.item(b.bibliography.zotero_id, limit=50, content='bib,html', format='https://www.zotero.org/styles/pontifical-biblical-institute')
            info_str += item[0] + "\n\n"

        # Create the response dictionary
        data = {
            'data': info_str.replace('\n','<br />'),
        }

        return JsonResponse(data)
class ProvenanceAjaxView(View):
    def get(self, request, *args, **kwargs):
        pk = self.request.GET.get('ms')
        ms_instance = get_object_or_404(Manuscripts, id=pk)
        skip_fields = ['manuscript']  # Add any other fields to skip
        
        # Sort the queryset by timeline_sequence
        info_queryset = ms_instance.ms_provenance.all().order_by('timeline_sequence')
        
        # Convert to dict
        info_dict = [get_obj_dictionary(entry, skip_fields) for entry in info_queryset]

        # Create markers list in the same order
        markers = []
        for p in info_queryset:
            name = '-'
            if p.place:
                name = p.place.repository_today_eng
                if not name or len(name) < 3:
                    name = p.place.repository_today_local_language

                markers.append({
                    'name': name,
                    'lon': p.place.longitude,
                    'lat': p.place.latitude,
                })

        # Handle debates
        debate = []
        for instance in info_queryset:
            debate_query = AttributeDebate.objects.filter(
                content_type__model='provenance', object_id=instance.id
            )
            for d in debate_query:
                bibliography = Bibliography.objects.get(id=d.bibliography_id)
                debate_dict = {
                    'id': d.id,
                    'instance_id': instance.id,
                    'field_name': d.field_name,
                    'text': d.text,
                    'bibliography': str(bibliography),
                    'bibliography_id': d.bibliography_id
                }
                debate.append(debate_dict)

        data = {
            'data': info_dict,
            'markers': markers,
            'debate': debate
        }

        return JsonResponse(data)

class AutocompleteView(View):
    def get(self, request):
        term = request.GET.get('term', '')
        items = Formulas.objects.filter(text__icontains=term)  # You can adjust the filter as needed
        items10 = items[:10]

        return items

class TraditionsAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return Traditions.objects.none()

        qs = Traditions.objects.all()

        genre = self.request.GET.get('genre', None)
        if genre:
            qs = qs.filter(genre__id=genre)

        if self.q:
            qs = qs.filter(name__icontains=self.q)

        return qs

class LiturgicalGenresAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return LiturgicalGenres.objects.none()

        qs = LiturgicalGenres.objects.all()

        if self.q:
            qs = qs.filter(title__icontains=self.q)

        return qs

class FormulaAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return Formulas.objects.none()

        qs = Formulas.objects.all()

        if self.q:
            qs = qs.filter(text__icontains=self.q)

        return qs

class ContentAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return Content.objects.none()

        qs = Content.objects.all()

        if self.q:
            qs = qs.filter(formula_text__icontains=self.q)

        return qs

class ManuscriptsAutocompleteMain(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return Manuscripts.objects.none()

        qs = Manuscripts.objects.all()

        projectId = self.request.GET.get('project_id', None)
        if projectId:
            qs = qs.filter(ms_projects__project__id=projectId)
        qs = qs.filter(display_as_main=True)


        if self.q:
            qs = qs.filter(
                Q(name__icontains=self.q) |
                Q(rism_id__icontains=self.q) |
                Q(foreign_id__icontains=self.q)
            )

        return qs

class ManuscriptsAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return Manuscripts.objects.none()

        qs = Manuscripts.objects.all()

        if self.q:
            qs = qs.filter(
                Q(name__icontains=self.q) |
                Q(rism_id__icontains=self.q) |
                Q(foreign_id__icontains=self.q)
            )

        return qs

class CllaProvenanceAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Pobierz unikalne wartości pola provenance, które nie są puste
        qs = Clla.objects.exclude(provenance__isnull=True).exclude(provenance__exact='').values('provenance').distinct()

        # Filtruj wyniki na podstawie wartości wprowadzonej przez użytkownika
        if self.q:
            qs = qs.filter(provenance__icontains=self.q)

        return qs

    def get_result_value(self, item):
        return str(item['provenance'])

    def get_result_label(self, item):
        return str(item['provenance'])


class CllaLiturgicalGenreAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Pobierz unikalne wartości pola liturgical_genre, które nie są puste
        qs = Clla.objects.exclude(liturgical_genre__isnull=True).exclude(liturgical_genre__exact='').values('liturgical_genre').distinct()

        # Filtruj wyniki na podstawie wartości wprowadzonej przez użytkownika
        if self.q:
            qs = qs.filter(liturgical_genre__icontains=self.q)

        return qs

    def get_result_value(self, item):
        return str(item['liturgical_genre'])

    def get_result_label(self, item):
        return str(item['liturgical_genre'])


class MSForeignIdAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Pobierz unikalne wartości pola foreign_id, które nie są puste
        qs = Manuscripts.objects.exclude(foreign_id__isnull=True).exclude(foreign_id__exact='').values('foreign_id').distinct()

        projectId = self.request.GET.get('project_id', None)
        if projectId:
            qs = qs.filter(ms_projects__project__id=projectId)
        qs = qs.filter(display_as_main=True)


        # Filtruj wyniki na podstawie wartości wprowadzonej przez użytkownika
        if self.q:
            qs = qs.filter(foreign_id__icontains=self.q)

        return qs

    def get_result_value(self, item):
        return str(item['foreign_id'])

    def get_result_label(self, item):
        return str(item['foreign_id'])

class MSShelfMarkAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Pobierz unikalne wartości pola foreign_id, które nie są puste
        qs = Manuscripts.objects.exclude(shelf_mark__isnull=True).exclude(shelf_mark__exact='').values('shelf_mark').distinct()

        projectId = self.request.GET.get('project_id', None)
        if projectId:
            qs = qs.filter(ms_projects__project__id=projectId)
        qs = qs.filter(display_as_main=True)

        # Filtruj wyniki na podstawie wartości wprowadzonej przez użytkownika
        if self.q:
            qs = qs.filter(shelf_mark__icontains=self.q)

        return qs

    def get_result_value(self, item):
        return str(item['shelf_mark'])

    def get_result_label(self, item):
        return str(item['shelf_mark'])

class MSContemporaryRepositoryPlaceAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Places.objects.filter(
            manuscripts__contemporary_repository_place__isnull=False,
            manuscripts__display_as_main=True
        ).distinct()

        if self.q:
            filters = Q()
            for field in Places._meta.fields:
                if field.get_internal_type() == 'CharField':
                    filters |= Q(**{field.name + '__icontains': self.q})
            qs = qs.filter(filters)

        return qs

    def get_result_label(self, item):
        return str(item)



class MSDatingAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = TimeReference.objects.exclude(
            manuscripts_dating__dating=None
        ).filter(
            manuscripts_dating__display_as_main=True
        ).distinct()

        if self.q:
            filters = Q(time_description__icontains=self.q)
            qs = qs.filter(filters)

        return qs


    def get_result_label(self, item):
        # Zwróć etykietę wyniku jako str() z obiektu Places
        return str(item)

class MSPlaceOfOriginsAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Places.objects.exclude(
            manuscripts_origin__place_of_origin=None
        ).filter(
            manuscripts_origin__display_as_main=True
        ).distinct()

        if self.q:
            filters = Q()
            for field in Places._meta.fields:
                if field.get_internal_type() == 'CharField':
                    filters |= Q(**{field.name + '__icontains': self.q})
            qs = qs.filter(filters)

        return qs

class MSProvenanceAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Pobieramy miejsca powiązane z Provenance, tylko te, które mają przypisany place
        qs = Places.objects.filter(
            provenance__manuscript__display_as_main=True,
            provenance__place__isnull=False
        ).distinct()

        # Filtrowanie po polach tekstowych na podstawie zapytania użytkownika
        if self.q:
            filters = Q()
            for field in Places._meta.fields:
                if field.get_internal_type() == 'CharField':
                    filters |= Q(**{field.name + '__icontains': self.q})
            qs = qs.filter(filters)

        return qs

    def get_result_label(self, item):
        # Zwróć etykietę wyniku jako str() z obiektu Places
        name = ''

        if item.city_historic_eng:
            name+=item.city_historic_eng
        elif item.city_today_eng:
            name+= item.city_today_eng

        if item.repository_historic_eng:
            if len(name)>1:
                name+=', '
            name+=item.repository_historic_eng
        elif item.repository_today_eng:
            if len(name)>1:
                name+=', '
            name+=item.repository_today_eng

        if len(name)<1:
            name = str(item)

        return name

class MSMainScriptAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = ScriptNames.objects.exclude(
            manuscripts__main_script=None
        ).filter(
            manuscripts__display_as_main=True
        ).distinct()

        if self.q:
            filters = Q(name__icontains=self.q)
            qs = qs.filter(filters)

        return qs


    def get_result_label(self, item):
        # Zwróć etykietę wyniku jako str() z obiektu Places
        return str(item)

class MSBindingDateAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = TimeReference.objects.exclude(
            manuscripts_binding_date__binding_date=None
        ).filter(
            manuscripts_binding_date__display_as_main=True
        ).distinct()

        if self.q:
            filters = Q(time_description__icontains=self.q)
            qs = qs.filter(filters)

        return qs


    def get_result_label(self, item):
        # Zwróć etykietę wyniku jako str() z obiektu Places
        return str(item)

class ContributorsAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return Contributors.objects.none()

        qs = Contributors.objects.all()

        if self.q:
            # Split  `self.q` into the words
            query_parts = self.q.split()
            
            # Build query
            query = Q()
            for part in query_parts:
                query &= (Q(initials__icontains=part) |
                        Q(first_name__icontains=part) |
                        Q(last_name__icontains=part))

                
            # Filter queryset
            qs = qs.filter(query)

        return qs

class SubjectAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return Subjects.objects.none()

        qs = Subjects.objects.all()

        if self.q:
            qs = qs.filter(name__icontains=self.q)

        return qs

class RiteNamesAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return RiteNames.objects.none()

        qs = RiteNames.objects.all()

        if self.q:
            qs = qs.filter(name__icontains=self.q)

        return qs

class GenreAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return Genre.objects.none()

        qs = Genre.objects.all()

        if self.q:
            #Name or short_name contains the query
            qs = qs.filter(Q(name__icontains=self.q) | Q(short_name__icontains=self.q))

        return qs


class ColoursAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return Colours.objects.none()

        qs = Colours.objects.all()

        if self.q:
            qs = qs.filter(name__icontains=self.q)

        return qs

class CharacteristicsAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return Characteristics.objects.none()

        qs = Characteristics.objects.all()

        if self.q:
            qs = qs.filter(name__icontains=self.q)

        return qs

#################################
class DecorationTypeAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return DecorationTypes.objects.none()

        qs = DecorationTypes.objects.all()
        qs = qs.filter(parent_type__isnull=True)

        if self.q:
            qs = qs.filter(name__icontains=self.q)

        return qs

class DecorationSubtypeAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return DecorationTypes.objects.none()

        qs = DecorationTypes.objects.all()
        qs = qs.filter(parent_type__isnull=False)

        if self.q:
            qs = qs.filter(name__icontains=self.q)

        return qs

class DecorationTechniquesAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return DecorationTechniques.objects.none()

        qs = DecorationTechniques.objects.all()

        if self.q:
            qs = qs.filter(name__icontains=self.q)

        return qs

class DecorationOrnamentedTextAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Decoration.objects.none()

        # Get distinct ornamented_text values        
        qs = Decoration.objects.exclude(ornamented_text__isnull=True).exclude(ornamented_text__exact='').values('ornamented_text').distinct()

        # Filter by ornamented_text if there's a search query
        if self.q:
            qs = qs.filter(ornamented_text__icontains=self.q)

        return qs


    def get_result_value(self, item):
        return str(item['ornamented_text'])

    def get_result_label(self, item):
        return str(item['ornamented_text'])

######################################
class ScriptNamesAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return ScriptNames.objects.none()

        qs = ScriptNames.objects.all()

        if self.q:
            qs = qs.filter(name__icontains=self.q)

        return qs

class BindingTypesAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return BindingTypes.objects.none()

        qs = BindingTypes.objects.all()

        if self.q:
            qs = qs.filter(name__icontains=self.q)

        return qs

class BindingStylesAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return BindingStyles.objects.none()

        qs = BindingStyles.objects.all()

        if self.q:
            qs = qs.filter(name__icontains=self.q)

        return qs

class BindingMaterialsAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return BindingMaterials.objects.none()

        qs = BindingMaterials.objects.all()

        if self.q:
            qs = qs.filter(name__icontains=self.q)

        return qs

class BindingDecorationTypeAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return BindingDecorationTypes.objects.none()

        qs = BindingDecorationTypes.objects.all()

        if self.q:
            qs = qs.filter(name__icontains=self.q)

        return qs

class BindingComponentsAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return BindingComponents.objects.none()

        qs = BindingComponents.objects.all()

        if self.q:
            qs = qs.filter(name__icontains=self.q)

        return qs

class MusicNotationNamesAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return MusicNotationNames.objects.none()

        qs = MusicNotationNames.objects.all()

        if self.q:
            qs = qs.filter(name__icontains=self.q)

        return qs


class BindingCategoryAutocomplete(autocomplete.Select2ListView):
    def get_list(self):
        # Retrieve the choices dynamically from the Binding model
        categories = Binding._meta.get_field('category').choices
        
        # If there's a query (self.q), filter the list of choices
        if self.q:
            return [category for category in categories if self.q.lower() in category[1].lower()]

        # Return all categories if no query is provided
        return categories

    def get(self, request, *args, **kwargs):
        # Get the filtered list of categories
        categories = self.get_list()

        # Format the choices as required by Select2 (id, text)
        results = [{"id": category[0], "text": category[1]} for category in categories]
        
        # Return the results as JSON response
        return JsonResponse({
            "results": results
        })


class BibliographyTitleAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return Bibliography.objects.none()

        qs = Bibliography.objects.all()

        if self.q:
            qs = qs.filter(title__icontains=self.q)

        return qs

class BibliographyAuthorAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return Bibliography.objects.none()

        qs = Bibliography.objects.all()

        if self.q:
            qs = qs.filter(author__icontains=self.q)

        return qs

    def get_result_label(self, item):
        return item.author

class FormulasAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return Formulas.objects.none()

        qs = Formulas.objects.all()

        if self.q:
            qs = qs.filter(text__icontains=self.q)

        return qs

    def get_result_label(self, item):
        return item.text

class RiteNamesAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return RiteNames.objects.none()

        qs = RiteNames.objects.all()

        if self.q:
            qs = qs.filter(name__icontains=self.q)

        return qs

    def get_result_label(self, item):
        return item.name

class PlacesAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Places.objects.none()

        qs = Places.objects.all()

        if self.q:
            qs = qs.filter(
                Q(place_type__icontains=self.q) |
                Q(country_today_eng__icontains=self.q) |
                Q(region_today_eng__icontains=self.q) |
                Q(city_today_eng__icontains=self.q) |
                Q(repository_today_eng__icontains=self.q) |
                Q(country_today_local_language__icontains=self.q) |
                Q(region_today_local_language__icontains=self.q) |
                Q(city_today_local_language__icontains=self.q) |
                Q(repository_today_local_language__icontains=self.q) |
                Q(country_historic_eng__icontains=self.q) |
                Q(region_historic_eng__icontains=self.q) |
                Q(city_historic_eng__icontains=self.q) |
                Q(repository_historic_eng__icontains=self.q) |
                Q(country_historic_local_language__icontains=self.q) |
                Q(region_historic_local_language__icontains=self.q) |
                Q(city_historic_local_language__icontains=self.q) |
                Q(repository_historic_local_language__icontains=self.q) |
                Q(country_historic_latin__icontains=self.q) |
                Q(region_historic_latin__icontains=self.q) |
                Q(city_historic_latin__icontains=self.q) |
                Q(repository_historic_latin__icontains=self.q)
            )

        return qs


class PlacesCountriesAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Places.objects.none()

        qs = Places.objects.all()

        if self.q:
            qs = qs.filter(
                Q(country_today_eng__icontains=self.q) |
                Q(country_today_local_language__icontains=self.q) |
                Q(country_historic_eng__icontains=self.q) |
                Q(country_historic_local_language__icontains=self.q) |
                Q(country_historic_latin__icontains=self.q)
            )

        # Group by the country fields to get unique results
        qs = qs.values(
            'country_today_eng'
        ).distinct()

        return qs

    def get_result_label(self, item):
        # Adjusting to handle dictionaries returned by `values()`
        if item.get('country_today_eng'):
            return item['country_today_eng']
        if item.get('country_today_local_language'):
            return item['country_today_local_language']
        if item.get('country_historic_eng'):
            return item['country_historic_eng']
        if item.get('country_historic_local_language'):
            return item['country_historic_local_language']
        if item.get('country_historic_latin'):
            return item['country_historic_latin']

        return '-'

    def get_result_value(self, item):
        # Use country_today_eng as the unique identifier for the value
        return item.get('country_today_eng') or item.get('country_today_local_language') or \
               item.get('country_historic_eng') or item.get('country_historic_local_language') or \
               item.get('country_historic_latin')

    def get_selected_result_label(self, item):
        # Use the same logic as get_result_label for the selected value
        return self.get_result_label(item)



        return '-'

@method_decorator(csrf_exempt, name='dispatch')
class ContentImportView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body.decode('utf-8'))
            if not isinstance(data, list):
                return JsonResponse({'info': 'error: Expected a list of dictionaries in request body'}, status=200)

            import_result = self.import_content(data)

            return import_result
                #return JsonResponse({'info': 'success'}, status=200)
        except Exception as e:
            return JsonResponse({'info': f'error: {str(e)}'}, status=200)


    def check_foreign_key_existence(self, table_name, foreign_key_value):
        # Sprawdź, czy wartość foreign_key_value istnieje w tabeli o nazwie table_name
        # W tym przykładzie zakładamy, że table_name to nazwa modelu Django
        try:
            model = globals()[table_name.capitalize()]  # Pobierz model na podstawie nazwy
            return model.objects.filter(pk=foreign_key_value).exists()  # Sprawdź istnienie rekordu z danym kluczem głównym
        except KeyError:
            # Obsłuż wyjątek, jeśli nie można odnaleźć modelu o danej nazwie
            return False

    def import_content(self, data):

        content_list = []

        try:
            for row in data:

                for key, value in row.items():
                    if value == '':
                        row[key] = None

                # Convert names to IDs
                new_liturgical_genre_id = None
                if 'liturgical_genre_id' in row:
                    new_liturgical_genre_id = self.get_id_by_name('LiturgicalGenres', row.get('liturgical_genre_id'), 'title')
                
                new_music_notation_id = None
                if 'music_notation_id' in row and row.get('music_notation_id') is not None:
                    # Get the music_notation_name ID from MusicNotationNames
                    music_notation_name_id = self.get_id_by_name('MusicNotationNames', row.get('music_notation_id'), 'name')
                    if music_notation_name_id is None:
                        return JsonResponse({'info': f'error: could not find value "{row.get("music_notation_id")}" in table MusicNotationNames'}, status=200)
                    
                    # Create a new ManuscriptMusicNotations entry
                    try:
                        manuscript_music_notation = ManuscriptMusicNotations(
                            manuscript_id=row.get('manuscript_id'),
                            music_notation_name_id=music_notation_name_id,
                            where_in_ms_from=row.get('where_in_ms_from') or "",
                            where_in_ms_to=row.get('where_in_ms_to') or "",
                            digital_page_number=row.get('digital_page_number'),
                            sequence_in_ms=row.get('sequence_in_ms') or 0,
                            dating=None,
                            original=None,
                            on_lines=None,
                            music_custos=None,
                            number_of_lines=None,
                            comment=None,
                            data_contributor_id=row.get('contributor_id')
                        )
                        manuscript_music_notation.save()
                        new_music_notation_id = manuscript_music_notation.id
                    except Exception as e:
                        return JsonResponse({'info': f'error: could not create ManuscriptMusicNotations entry for "{row.get("music_notation_id")}": {str(e)}'}, status=200)

                new_function_id = None
                if 'function_id' in row:
                    new_function_id = self.get_id_by_name('ContentFunctions', row.get('function_id'))
                
                new_subfunction_id = None
                if 'subfunction_id' in row:
                    new_subfunction_id = self.get_id_by_name('ContentFunctions', row.get('subfunction_id'))
                
                new_section_id = None
                if 'section_id' in row:
                    new_section_id = self.get_id_by_name('Sections', row.get('section_id'))
                
                new_subsection_id = None
                if 'subsection_id' in row:
                    new_subsection_id = self.get_id_by_name('Sections', row.get('subsection_id'))

                new_layer = None
                if 'layer' in row:
                    new_layer = self.get_id_by_name('Layer', row.get('layer'), 'short_name')

                new_mass_hour = None
                if 'mass_hour' in row:
                    new_mass_hour = self.get_id_by_name('MassHour', row.get('mass_hour'), 'short_name')

                new_genre = None
                if 'genre' in row:
                    new_genre = self.get_id_by_name('Genre', row.get('genre'), 'short_name')
                print('new_genre', new_genre)

                new_season_month = None
                if 'season_month' in row:
                    new_season_month = self.get_id_by_name('SeasonMonth', row.get('season_month'), 'short_name')
                print('new_season_month', new_season_month)

                new_week = None
                if 'week' in row:
                    new_week = self.get_id_by_name('Week', row.get('week'), 'short_name')
                print('new_week', new_week)

                new_day = None
                if 'day' in row:
                    new_day = self.get_id_by_name('Day', row.get('day'), 'short_name')
                print('new_day', new_day)

                new_proper_texts = None
                if 'proper_texts' in row and row.get('proper_texts') is not None:
                    value = str(row.get('proper_texts')).lower()
                    if value in ['1', 'true']:
                        new_proper_texts = True
                    elif value in ['0', 'false']:
                        new_proper_texts = False
                    # Empty string or other values result in None (null)

                new_edition_index = None
                if 'edition_index' in row and row.get('edition_index') :
                    #print(row.get('edition_index'))
                    parts = row.get('edition_index').split(" c.")
                    if len(parts) < 2:
                        return JsonResponse({'info': f'error: edition_index "{row.get("edition_index")}" is invalid'}, status=200)
                    bibliography_shortname= parts[0]
                    feast_rubric_sequence= parts[1]
                    new_edition_index = self.get_edition_content_id_by_fields('EditionContent', bibliography_shortname, feast_rubric_sequence)
                
                if new_liturgical_genre_id == None and row.get('liturgical_genre_id') != None :
                    return JsonResponse({'info': 'error: could not find value "'+row.get('liturgical_genre_id')+'" in table LiturgicalGenres'}, status=200)
                if new_music_notation_id == None and row.get('music_notation_id') != None :
                    return JsonResponse({'info': 'error: could not create ManuscriptMusicNotations entry for "'+row.get('music_notation_id')+'" in table ManuscriptMusicNotations'}, status=200)
                if new_function_id == None and row.get('function_id')  != None :
                    return JsonResponse({'info': 'error: could not find value "'+row.get('function_id') +'" in table ContentFunctions'}, status=200)
                if new_subfunction_id == None and row.get('subfunction_id')  != None :
                    return JsonResponse({'info': 'error: could not find value "'+row.get('subfunction_id') +'" in table ContentFunctions'}, status=200)
                if new_section_id == None and row.get('section_id')  != None :
                    return JsonResponse({'info': 'error: could not find value "'+row.get('section_id') +'" in table Sections'}, status=200)
                if new_subsection_id == None and row.get('subsection_id')  != None :
                    return JsonResponse({'info': 'error: could not find value "'+row.get('subsection_id') +'" in table Sections'}, status=200)
                if new_layer == None and row.get('layer') != None :
                    return JsonResponse({'info': 'error: could not find value "'+row.get('layer')+'" in table Layer'}, status=200)
                if new_mass_hour == None and row.get('mass_hour') != None :
                    return JsonResponse({'info': 'error: could not find value "'+row.get('mass_hour')+'" in table MassHour'}, status=200)
                if new_genre == None and row.get('genre') != None :
                    return JsonResponse({'info': 'error: could not find value "'+row.get('genre')+'" in table Genre'}, status=200)
                if new_season_month == None and row.get('season_month') != None :
                    return JsonResponse({'info': 'error: could not find value "'+row.get('season_month')+'" in table SeasonMonth'}, status=200)
                if new_week == None and row.get('week') != None :
                    return JsonResponse({'info': 'error: could not find value "'+row.get('week')+'" in table Week'}, status=200)
                if new_day == None and row.get('day') != None :
                    return JsonResponse({'info': 'error: could not find value "'+row.get('day')+'" in table Day'}, status=200)
                if new_edition_index == None and row.get('edition_index')  != None :
                    return JsonResponse({'info': 'error: could not find value "'+row.get('edition_index') +'" in table EditionContent'}, status=200)



                row['liturgical_genre_id'] = new_liturgical_genre_id 
                row['music_notation_id'] = new_music_notation_id
                row['function_id'] = new_function_id
                row['subfunction_id'] = new_subfunction_id 
                row['section_id'] = new_section_id
                row['subsection_id'] = new_subsection_id
                row['layer'] = new_layer
                row['mass_hour'] = new_mass_hour
                row['genre'] = new_genre
                row['season_month'] = new_season_month
                row['week'] = new_week
                row['day'] = new_day
                row['proper_texts'] = new_proper_texts
                row['edition_index'] = new_edition_index


                    # Sprawdź, czy wartość klucza obcego 'formula_id' jest poprawna
                if 'formula_id' in row and isinstance(row['formula_id'], (int, str)) and row['formula_id']:
                    formula_id = row['formula_id']
                    if not self.check_foreign_key_existence('formulas', formula_id):
                        return JsonResponse({'info': f'error: could not find value "{formula_id}" in table formulas'}, status=200)


                content = Content(
                    manuscript_id=row.get('manuscript_id'),
                    formula_id=row.get('formula_id'),
                    rubric_id=row.get('rubric_id'),
                    rubric_name_from_ms=row.get('rubric_name_from_ms'),
                    subrubric_name_from_ms=row.get('subrubric_name_from_ms'),
                    rubric_sequence=row.get('rubric_sequence_in_the_MS'),
                    formula_text=row.get('formula_text_from_ms'),
                    sequence_in_ms=row.get('sequence_in_ms'),
                    where_in_ms_from=row.get('where_in_ms_from'),
                    where_in_ms_to=row.get('where_in_ms_to'),
                    digital_page_number=row.get('digital_page_number'),
                    original_or_added=row.get('original_or_added'),
                    liturgical_genre_id=row.get('liturgical_genre_id'),
                    quire_id=row.get('quire_id'),
                    section_id=row.get('section_id'),
                    subsection_id=row.get('subsection_id'),
                    music_notation_id=row.get('music_notation_id'),
                    function_id=row.get('function_id'),
                    subfunction_id=row.get('subfunction_id'),
                    biblical_reference=row.get('biblical_reference'),
                    reference_to_other_items=row.get('reference_to_other_items'),
                    similarity_by_user=row.get('similarity_by_user'),
                    #entry_date=row.get('entry_date'),
                    edition_index_id=row.get('edition_index'),
                    edition_subindex=row.get('edition_subindex'),
                    comments=row.get('comments'),

                    layer_id=row.get('layer'),
                    mass_hour_id=row.get('mass_hour'),
                    genre_id=row.get('genre'),
                    season_month_id=row.get('season_month'),
                    week_id=row.get('week'),
                    day_id=row.get('day'),
                    proper_texts=row.get('proper_texts'),


                    # Add more fields as needed
                )

                # Print AutoField values for inspection
                #auto_field_values = {field.attname: getattr(content, field.attname) for field in content._meta.fields if isinstance(field, (models.AutoField, models.BigAutoField))}
                #print(f"AutoField values: {auto_field_values}")

                #content.authors.set(row.get('authors', []))
                content.data_contributor_id = row.get('contributor_id')

                #content.save()
                content_list.append(content)

            ##

            try:
                for content in content_list:
                    content.save()
            except Exception as e:
                failing_row_index = content_list.index(content) if content in content_list else -1
                if failing_row_index >= 0:
                    failing_row = data[failing_row_index]
                else:
                    failing_row = {}  # Fallback
                return JsonResponse({'info': f'error: could not find value to create foreign key in row {failing_row_index + 1}. ERROR: {str(e)}'}, status=200)

        except Exception as e:
            # Log the error or handle it accordingly
            # Importing none if there is an error in any row
            return JsonResponse({'info': f'error: {str(e)}'}, status=200)


        return JsonResponse({'info': 'success'}, status=200)


    def get_id_by_name(self, model_name, name, field_name='name'):
        model = apps.get_model(app_label='indexerapp', model_name=model_name)
        obj = model.objects.filter(**{f'{field_name}__iexact': name}).first()
        return obj.id if obj else None

    def get_edition_content_id_by_fields(self, model_name, bibliography_shortname, feast_rubric_sequence):
        model = apps.get_model(app_label='indexerapp', model_name=model_name)
        obj = model.objects.filter(bibliography__shortname__iexact=bibliography_shortname, feast_rubric_sequence=feast_rubric_sequence).first()
        return obj.id if obj else None

@method_decorator(csrf_exempt, name='dispatch')
class ManuscriptsImportView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body.decode('utf-8'))
            import_result = self.import_data(data)

            return import_result
            #return JsonResponse({'info': 'success'}, status=200)
        except Exception as e:
            return JsonResponse({'info': f'exception: {str(e)}'}, status=200)

    def import_data(self, data):

        content_list = []

        try:
            for row in data:

                for key, value in row.items():
                    if value == '':
                        row[key] = None

                # Convert names to IDs
                new_dating = self.get_id_by_name('TimeReference', row.get('dating'), 'time_description')
                if new_dating == None and row['dating'] != None :
                    return JsonResponse({'info': 'error: could not find value "'+row['dating']+'" in table TimeReference'}, status=200)
                row['dating'] = new_dating 

                #print('contemporary repository place in row:')
                #print(row['contemporary_repository_place'])

                                

                if row['contemporary_repository_place']:
                    new_contemporary_repository_place = self.get_id_by_name('Places', row.get('contemporary_repository_place'), 'repository_today_local_language')
                    if new_contemporary_repository_place == None and row['contemporary_repository_place'] != None :
                        return JsonResponse({'info': 'error: could not find value "'+row['contemporary_repository_place']+'" in table Places'}, status=200)
                    row['contemporary_repository_place'] = new_contemporary_repository_place 

                #print('contemporary repository place in row:')
                #print(row['contemporary_repository_place'])                

                #print('place_of_origin in row:')
                #print(row['place_of_origin'])   

                if row['place_of_origin']:
                    new_place_of_origin = self.get_id_by_name('Places', row.get('place_of_origin'), 'repository_today_eng')
                    if new_place_of_origin == None and row['place_of_origin'] != None :
                        return JsonResponse({'info': 'error: could not find value "'+row['place_of_origin']+'" in table Places'}, status=200)
                    row['place_of_origin'] = new_place_of_origin 
                
                #print('place_of_origin in row:')
                #print(row['place_of_origin'])   

                if row['main_script']:
                    new_main_script = self.get_id_by_name('ScriptNames', row.get('main_script'), 'name')
                    if new_main_script == None and row['main_script'] != None :
                        return JsonResponse({'info': 'error: could not find value "'+row['main_script']+'" in table ScriptNames'}, status=200)
                    row['main_script'] = new_main_script 
                    
                if row['binding_date']:
                    new_binding_date = self.get_id_by_name('TimeReference', row.get('binding_date'), 'time_description')
                    if new_binding_date == None and row['binding_date'] != None :
                        return JsonResponse({'info': 'error: could not find value "'+row['binding_date']+'" in table TimeReference'}, status=200)
                    row['binding_date'] = new_binding_date 

                if row['binding_place']:
                    new_binding_place = self.get_id_by_name('Places', row.get('binding_place'), 'repository_today_eng')
                    if new_binding_place == None and row['binding_place'] != None :
                        return JsonResponse({'info': 'error: could not find value "'+row['binding_place']+'" in table Places'}, status=200)
                    row['binding_place'] = new_binding_place 

                if row.get('decorated') == 'yes' :
                    row['decorated']=True
                elif row.get('decorated') == 'no' :
                    row['decorated']=False
                elif row.get('decorated') == None :
                    row['decorated']=None
                else:
                    return JsonResponse({'info': 'error: "decorated" can be only "yes", "no" or empty' }, status=200)

                if row.get('music_notation') == 'yes' :
                    row['music_notation']=True
                elif row.get('music_notation') == 'no' :
                    row['music_notation']=False
                elif row.get('music_notation') == None :
                    row['music_notation']=None
                else:
                    return JsonResponse({'info': 'error: "music_notation" can be only "yes", "no" or empty' }, status=200)

                if row.get('display_as_main') == 'yes' :
                    row['display_as_main']=True
                elif row.get('display_as_main') == 'no' :
                    row['display_as_main']=False
                elif row.get('display_as_main') == None :
                    row['display_as_main']=None
                else:
                    return JsonResponse({'info': 'error: "display_as_main" can be only "yes", "no" or empty' }, status=200)



                content = Manuscripts(
                    id = row.get('id'),
                    name = row.get('name'),
                    rism_id = row.get('rism_id'),
                    foreign_id = row.get('foreign_id'),
                    contemporary_repository_place_id = row.get('contemporary_repository_place'),
                    shelf_mark = row.get('shelf_mark'),
                    liturgical_genre_comment = row.get('liturgical_genre_comment'),
                    common_name = row.get('common_name'),
                    dating_id = row.get('dating'),
                    dating_comment = row.get('dating_comment'),
                    place_of_origin_id = row.get('place_of_origin'),
                    place_of_origin_comment = row.get('place_of_origin_comment'),
                    main_script_id = row.get('main_script'),
                    how_many_columns_mostly = row.get('how_many_columns_mostly'),
                    lines_per_page_usually =  row.get('lines_per_page_usually'),
                    how_many_quires = row.get('how_many_quires'),
                    quires_comment = row.get('quires_comment'),
                    foliation_or_pagination = row.get('foliation_or_pagination'),
                    decorated = row.get('decorated'),
                    decoration_comments = row.get('decoration_comments'),
                    music_notation = row.get('music_notation'),
                    music_notation_comments = row.get('music_notation_comments'),
                    binding_date_id = row.get('binding_date'),
                    binding_place_id =  row.get('binding_place'),
                    links = row.get('links'),
                    iiif_manifest_url = row.get('iiif_manifest_url'),

                    form_of_an_item = row.get('form_of_an_item'),
                    connected_ms = row.get('connected_ms'),
                    where_in_connected_ms = row.get('where_in_connected_ms'),
                    general_comment = row.get('general_comment'),
                    additional_url = row.get('additional_url'),
                    display_as_main = row.get('display_as_main'),

                    image =  row.get('image'),

                    data_contributor_id =  row.get('contributor_id'),
                        
                )

                # Print AutoField values for inspection
                #auto_field_values = {field.attname: getattr(content, field.attname) for field in content._meta.fields if isinstance(field, (models.AutoField, models.BigAutoField))}
                #print(f"AutoField values: {auto_field_values}")

                #content.authors.set(row.get('authors', []))
                #content.data_contributor_id = row.get('contributor_id')

                #content.save()
                content_list.append(content)

            for content in content_list:
                content.save()
        
        except Exception as e:
            # Log the error or handle it accordingly
            # Importing none if there is an error in any row
            return JsonResponse({'info': f'error: {str(e)}'}, status=200)


        return JsonResponse({'info': 'success'}, status=200)


    def get_id_by_name(self, model_name, name, field_name='name'):
        model = apps.get_model(app_label='indexerapp', model_name=model_name)
        obj = model.objects.filter(**{f'{field_name}__iexact': name}).first()
        return obj.id if obj else None


@method_decorator(csrf_exempt, name='dispatch')
class TimeReferenceImportView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body.decode('utf-8'))
            import_result = self.import_data(data)
            return import_result
        except Exception as e:
            return JsonResponse({'info': f'exception: {str(e)}'}, status=200)

    def import_data(self, data):
        content_list = []

        try:
            for row in data:

                for key, value in row.items():
                    if value == '':
                        row[key] = None

                # Convert names to IDs
                #new_liturgical_genre_id = self.get_id_by_name('LiturgicalGenres', row.get('liturgical_genre_id'), 'title')
                
                #if new_liturgical_genre_id == None and row['liturgical_genre_id'] != None :
                #    return JsonResponse({'info': 'error: could not find value "'+row['liturgical_genre_id']+'" in table LiturgicalGenres'}, status=200)
                
                #row['liturgical_genre_id'] = new_liturgical_genre_id 

                content = TimeReference(
                    time_description = row.get('time_description'),
                    century_from = row.get('century_from'),
                    century_to = row.get('century_to'),
                    year_from = row.get('year_from'),
                    year_to = row.get('year_to'),
                )


                #content.authors.set(row.get('authors', []))
                #content.data_contributor_id = row.get('contributor_id')

                #content.save()
                content_list.append(content)

            for content in content_list:
                content.save()
        
        except Exception as e:
            # Log the error or handle it accordingly
            # Importing none if there is an error in any row
            return JsonResponse({'info': f'error: {str(e)}'}, status=200)


        return JsonResponse({'info': 'success'}, status=200)


    def get_id_by_name(self, model_name, name, field_name='name'):
        model = apps.get_model(app_label='indexerapp', model_name=model_name)
        obj = model.objects.filter(**{f'{field_name}__iexact': name}).first()
        return obj.id if obj else None

@method_decorator(csrf_exempt, name='dispatch')
class EditionContentImportView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body.decode('utf-8'))
            import_result = self.import_data(data)
            return import_result
        except Exception as e:
            return JsonResponse({'info': f'error: {str(e)}'}, status=200)

    def import_data(self, data):
        content_list = []

        try:
            for row in data:

                for key, value in row.items():
                    if value == '':
                        row[key] = None

                # Convert names to IDs
                new_rubric_name_standarized = self.get_id_by_name('RiteNames', row.get('rubric_name_standarized'), 'name')
                if new_rubric_name_standarized == None and row['rubric_name_standarized'] != None :
                    return JsonResponse({'info': 'error: could not find value "'+row['rubric_name_standarized']+'" in table RiteNames'}, status=200)
                row['rubric_name_standarized'] = new_rubric_name_standarized 

                new_function = self.get_id_by_name('ContentFunctions', row.get('function'))
                if new_function == None and row['function'] != None :
                    return JsonResponse({'info': 'error: could not find value "'+row['function']+'" in table ContentFunctions'}, status=200)
                row['function'] = new_function
                
                new_subfunction = self.get_id_by_name('ContentFunctions', row.get('subfunction'))
                if new_subfunction == None and row['subfunction'] != None :
                    return JsonResponse({'info': 'error: could not find value "'+row['subfunction']+'" in table ContentFunctions'}, status=200)
                row['subfunction'] = new_subfunction 



                content = EditionContent(
                    bibliography_id = row.get('bibliography_id'),
                    formula_id = row.get('formula_id'),
                    rubric_name_standarized_id = row.get('rubric_name_standarized'),
                    feast_rubric_sequence = row.get('feast_rubric_sequence'),
                    subsequence = row.get('subsequence'),
                    page = row.get('page'),
                    function_id = row.get('function'),
                    subfunction_id = row.get('subfunction'),
                )


                #content.authors.set(row.get('authors', []))
                content.data_contributor_id = row.get('contributor_id')

                #content.save()
                content_list.append(content)

            for content in content_list:
                content.save()
        
        except Exception as e:
            # Log the error or handle it accordingly
            # Importing none if there is an error in any row
            return JsonResponse({'info': f'error: {str(e)}'}, status=200)


        return JsonResponse({'info': 'success'}, status=200)


    def get_id_by_name(self, model_name, name, field_name='name'):
        model = apps.get_model(app_label='indexerapp', model_name=model_name)
        obj = model.objects.filter(**{f'{field_name}__iexact': name}).first()
        return obj.id if obj else None



@method_decorator(csrf_exempt, name='dispatch')
class CllaImportView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body.decode('utf-8'))
            import_result = self.import_data(data)
            return import_result
        except Exception as e:
            return JsonResponse({'info': f'error: {str(e)}'}, status=200)

    def import_data(self, data):
        content_list = []

        try:
            for row in data:

                for key, value in row.items():
                    if value == '':
                        row[key] = None

                # Convert names to IDs
                if row.get('dating'):
                    new_dating = self.get_id_by_name('TimeReference', row.get('dating'), 'time_description')
                    if new_dating == None and row['dating'] != None :
                        return JsonResponse({'info': 'error: could not find value "'+row['dating']+'" in table TimeReference'}, status=200)
                    row['dating'] = new_dating 

                """
                new_provenance = 
                
                new_provenance = self.get_id_by_name('Places', row.get('provenance'), 'repository_today_eng')

                if new_provenance == None and row['provenance'] != None :
                    new_provenance = self.get_id_by_name('Places', row.get('provenance'), 'repository_today_eng')

                if new_provenance == None and row['provenance'] != None :
                    return JsonResponse({'info': 'error: could not find value "'+row['provenance']+'" in table Places'}, status=200)
                row['provenance'] = new_provenance 
                """


                content = Clla(
                    manuscript_id = row.get('manuscript_id'),
                    clla_no = row.get('clla_no'),
                    liturgical_genre = row.get('liturgical_genre'),
                    dating_id = row.get('dating'),
                    dating_comment = row.get('dating_comment'),
                    provenance = row.get('provenance'),
                    provenance_comment = row.get('provenance_comment'),
                    comment = row.get('comment'),
                )

                #content.authors.set(row.get('authors', []))
                #content.data_contributor_id = row.get('contributor_id')

                #content.save()
                content_list.append(content)

            for content in content_list:
                content.save()
        
        except Exception as e:
            # Log the error or handle it accordingly
            # Importing none if there is an error in any row
            return JsonResponse({'info': f'error: {str(e)}'}, status=200)


        return JsonResponse({'info': 'success'}, status=200)


    def get_id_by_name(self, model_name, name, field_name='name'):
        model = apps.get_model(app_label='indexerapp', model_name=model_name)
        obj = model.objects.filter(**{f'{field_name}__iexact': name}).first()
        return obj.id if obj else None


@method_decorator(csrf_exempt, name='dispatch')
class PlacesImportView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body.decode('utf-8'))
            import_result = self.import_data(data)
            return import_result
        except Exception as e:
            return JsonResponse({'info': f'error: {str(e)}'}, status=200)

    def import_data(self, data):
        content_list = []

        try:
            for row in data:

                for key, value in row.items():
                    if value == '':
                        row[key] = None


                content = Places(
                    longitude = row.get('longitude'),
                    latitude = row.get('latitude'),

                    place_type = row.get('place_type'),

                    country_today_eng = row.get('country_today_eng'),
                    region_today_eng = row.get('region_today_eng'),
                    city_today_eng = row.get('city_today_eng'),
                    repository_today_eng = row.get('repository_today_eng'),

                    country_today_local_language = row.get('country_today_local_language'),
                    region_today_local_language = row.get('region_today_local_language'),
                    city_today_local_language = row.get('city_today_local_language'),
                    repository_today_local_language = row.get('repository_today_local_language'),

                    country_historic_eng = row.get('country_historic_eng'),
                    region_historic_eng = row.get('region_historic_eng'),
                    city_historic_eng = row.get('city_historic_eng'),
                    repository_historic_eng = row.get('repository_historic_eng'),

                    country_historic_local_language = row.get('country_historic_local_language'),
                    region_historic_local_language = row.get('region_historic_local_language'),
                    city_historic_local_language = row.get('city_historic_local_language'),
                    repository_historic_local_language = row.get('repository_historic_local_language'),

                    country_historic_latin = row.get('country_historic_latin'),
                    region_historic_latin = row.get('region_historic_latin'),
                    city_historic_latin = row.get('city_historic_latin'),
                    repository_historic_latin = row.get('repository_historic_latin'),
                )

                #content.authors.set(row.get('authors', []))
                #content.data_contributor_id = row.get('contributor_id')

                #content.save()
                content_list.append(content)

            for content in content_list:
                content.save()
        
        except Exception as e:
            # Log the error or handle it accordingly
            # Importing none if there is an error in any row
            return JsonResponse({'info': f'error: {str(e)}'}, status=200)


        return JsonResponse({'info': 'success'}, status=200)


    def get_id_by_name(self, model_name, name, field_name='name'):
        model = apps.get_model(app_label='indexerapp', model_name=model_name)
        obj = model.objects.filter(**{f'{field_name}__iexact': name}).first()
        return obj.id if obj else None

@method_decorator(csrf_exempt, name='dispatch')
class RiteNamesImportView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body.decode('utf-8'))
            import_result = self.import_data(data)
            return import_result
        except Exception as e:
            return JsonResponse({'info': f'error: {str(e)}'}, status=200)

    def import_data(self, data):
        content_list = []

        try:
            for row in data:

                for key, value in row.items():
                    if value == '':
                        row[key] = None

                # Convert names to IDs
                new_section = self.get_id_by_name('Sections', row.get('section'), 'name')
                
                if new_section == None and row['section'] != None :
                    return JsonResponse({'info': 'error: could not find value "'+row['section']+'" in table Sections'}, status=200)
                
                row['section'] = new_section

                if row.get('votive') == 'yes' :
                    row['votive']=True
                elif row.get('votive') == 'no' :
                    row['votive']=False
                elif row.get('votive') == None :
                    row['votive']=None
                else:
                    return JsonResponse({'info': 'error: "votive" can be only "yes", "no" or empty' }, status=200)


                content = RiteNames(
                    name = row.get('name'),
                    english_translation  = row.get('english_translation'),
                    section_id  = row.get('section'),
                    votive  = row.get('votive'),
                )


                #content.authors.set(row.get('authors', []))
                #content.data_contributor_id = row.get('contributor_id')

                #content.save()
                content_list.append(content)

            for content in content_list:
                content.save()
        
        except Exception as e:
            # Log the error or handle it accordingly
            # Importing none if there is an error in any row
            return JsonResponse({'info': f'error: {str(e)}'}, status=200)


        return JsonResponse({'info': 'success'}, status=200)


    def get_id_by_name(self, model_name, name, field_name='name'):
        model = apps.get_model(app_label='indexerapp', model_name=model_name)
        obj = model.objects.filter(**{f'{field_name}__iexact': name}).first()
        return obj.id if obj else None

@method_decorator(csrf_exempt, name='dispatch')
class FormulasImportView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body.decode('utf-8'))
            import_result = self.import_data(data)
            return import_result
        except Exception as e:
            return JsonResponse({'info': f'error: {str(e)}'}, status=200)

    def import_data(self, data):
        content_list = []

        try:
            for row in data:

                for key, value in row.items():
                    if value == '':
                        row[key] = None

                # Convert names to IDs

                content = Formulas(
                    id = row.get('id'),
                    co_no  = row.get('co_no'),
                    text  = row.get('text')
                )


                #content.authors.set(row.get('authors', []))
                #content.data_contributor_id = row.get('contributor_id')

                #content.save()
                content_list.append(content)

            for content in content_list:
                content.save()
        
        except Exception as e:
            # Log the error or handle it accordingly
            # Importing none if there is an error in any row
            return JsonResponse({'info': f'error: {str(e)}'}, status=200)


        return JsonResponse({'info': 'success'}, status=200)


    def get_id_by_name(self, model_name, name, field_name='name'):
        model = apps.get_model(app_label='indexerapp', model_name=model_name)
        obj = model.objects.filter(**{f'{field_name}__iexact': name}).first()
        return obj.id if obj else None

@method_decorator(csrf_exempt, name='dispatch')
class BibliographyImportView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body.decode('utf-8'))
            import_result = self.import_data(data)
            return import_result
        except Exception as e:
            return JsonResponse({'info': f'error: {str(e)}'}, status=200)

    def import_data(self, data):
        content_list = []

        try:
            for row in data:

                for key, value in row.items():
                    if value == '':
                        row[key] = None

                # Convert names to IDs
                content = Bibliography(
                    title = row.get('title'),
                    author  = row.get('author'),
                    shortname  = row.get('shortname'),
                    year = row.get('year'),
                    zotero_id  = row.get('zotero_id'),
                    hierarchy  = row.get('hierarchy')
                )


                #content.authors.set(row.get('authors', []))
                #content.data_contributor_id = row.get('contributor_id')

                #content.save()
                content_list.append(content)

            for content in content_list:
                content.save()
        
        except Exception as e:
            # Log the error or handle it accordingly
            # Importing none if there is an error in any row
            return JsonResponse({'info': f'error: {str(e)}'}, status=200)


        return JsonResponse({'info': 'success'}, status=200)


    def get_id_by_name(self, model_name, name, field_name='name'):
        model = apps.get_model(app_label='indexerapp', model_name=model_name)
        obj = model.objects.filter(**{f'{field_name}__iexact': name}).first()
        return obj.id if obj else None


class Index(View):
    template = 'index.html'
    login_url = '/login/'

    def get(self, request):
        return HttpResponseRedirect('/static/page.html?p=about')

        #manuscripts = Manuscripts.objects.all()
        #content = Content.objects.all()
        #formulas = Formulas.objects.all()
        
        #return render(request,
        #    self.template,
        #    {
        #        'manuscripts': manuscripts,
        #        #'rites': rites,
        #        'content': content,
        #        'formulas': formulas
        #    }
        #)

class ManuscriptsView(LoginRequiredMixin, View):
    template = 'manuscripts.html'
    login_url = '/login/'

    def get(self, request):

        return HttpResponseRedirect('/static/page.html?p=manuscripts')

        #manuscripts = Manuscripts.objects.all()
        #return render(request, self.template, {'manuscripts': manuscripts})


def get_object_attr_dict(obj):
    if obj is None:
        return None

    #model = obj._meta.model
    info = model_to_dict(obj)

    info_strings = {}
    #Translation model to string values:
    for field_name, value in info.items():
        if hasattr(obj, field_name):
            field = getattr(obj, field_name)
            info_strings[field_name]=str(field)

    return info_strings

def foliation(value):
    if value is None:
        return ""

    # valueRnd = math.floor(float(value))
    # valueRemaining = float(value) - valueRnd;

    # retStr = str(valueRnd)
    # if valueRemaining > 0.09 and valueRemaining  < 0.11:
    #     retStr += 'r'
    # elif valueRemaining > 0.19 and valueRemaining  < 0.21:
    #     retStr += 'v'

    # return retStr

    return value

def get_obj_dictionary(obj, skip_fields):
    if obj is None:
        return None
    
    obj_dict = model_to_dict(obj)
    
    # Exclude specified fields
    for field in skip_fields:
        obj_dict.pop(field, None)

    info_strings = {}

    #Translation model to string values:
    for field_name, value in obj_dict.items():
        if hasattr(obj, field_name):
            field = getattr(obj, field_name)
            if isinstance(field, bool):
                info_strings[field_name] = "Yes" if field else "No"
            elif field is None:
                info_strings[field_name] = "-"
            elif field_name == 'where_in_ms_from' or field_name == 'where_in_ms_to':
                info_strings[field_name] =foliation(field)
            elif field_name == 'form_of_an_item':
                form_of_an_item_map = {key: value.lower() for key, value in obj._meta.get_field('form_of_an_item').choices}
                info_strings[field_name] = form_of_an_item_map.get(field, field)  # Default to value if key not found     
            elif field_name == 'authors' and type(obj.authors) is not str:
                info_strings[field_name] = [str(author) for author in obj.authors.all()]       
            else:
                info_strings[field_name]=str(field)

    return info_strings

from django.core.paginator import Paginator
from django.http import JsonResponse

"""
class MSContentView(ServerSideDatatableView):
    instance = get_object_or_404(Manuscripts, id=2)
    queryset = instance.ms_content.all()
    columns = ['formula', 'rite']


class MSContentView(View):
    template_name = 'ms_content.html'
    items_per_page = 10  # Adjust this based on your preference

    def get(self, request, pk):
        skip_fields = ['id', 'manuscript']
        instance = get_object_or_404(Manuscripts, id=pk)
        objects = instance.ms_content.all()

        # Paginate the queryset
        paginator = Paginator(objects, self.items_per_page)
        draw = int(request.GET.get('draw', 1))
        print('draw: ', draw)
        start = float(request.GET.get('start', 1))
        print('start: ', start)
        length = float(request.GET.get('length', 1))
        print('length: ', length)
        search = request.GET.get('search', 1)
        print('search: ', search)

        page = math.floor(start/length)+1


        paginated_objects = paginator.page(page)


        obj_dict = [get_obj_dictionary(entry, skip_fields) for entry in paginated_objects]

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            data = {
                'draw': draw,
                'recordsTotal': paginator.num_pages*length,
                "recordsFiltered": paginator.num_pages*length,
                'headers': list(obj_dict[0].keys()),
                'data': obj_dict,
                'total_pages': paginator.num_pages,
                'current_page': paginated_objects.number,
            }
            return JsonResponse(data)

        return render(request, self.template_name, {'obj_dict': obj_dict})
"""

"""
class MSMusicNotationView(View):
    template_name = 'music_notation.html'

    def get(self, request, pk):
        skip_fields = [ 'manuscript']
        instance = get_object_or_404(Manuscripts, id=pk)
        music_notation_objects = instance.ms_music_notation.all()

        print('music_notation_objects')
        print(music_notation_objects)


        music_notation = [get_obj_dictionary(entry, skip_fields) for entry in music_notation_objects]

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            data = {
                'headers': list(music_notation[0].keys()),
                'rows': music_notation,
            }
            return JsonResponse(data)

        return render(request, self.template_name, {'music_notation': music_notation})
"""

@method_decorator(csrf_exempt, name='dispatch')
class ManuscriptDetail(LoginRequiredMixin, View):
    template = 'manuscript_detail.html'
    login_url = '/login/'


    def get(self, request, pk):
        return HttpResponseRedirect('/static/page.html?p=manuscripts')


        #instance = get_object_or_404(Manuscripts, id=pk)

        #skip_fields = ['id', 'manuscript', 'entry_date']  # Add any other fields to skip


        #Main info:
        #info = get_obj_dictionary(instance,[])

        #MS Comments:
        #debate = AttributeDebate.objects.filter(content_type=ContentType.objects.get_for_model(Manuscripts), object_id=pk)

        #MS Codicology:
        #codicology = get_obj_dictionary(instance.ms_codicology.first(),skip_fields)

        #Layouts:
        #layouts = instance.ms_layouts.all().values()
        #layouts_objects = instance.ms_layouts.all()
        #layouts = [get_obj_dictionary(entry, skip_fields) for entry in layouts_objects]

        #Music notation
        #music_notation_objects = instance.ms_music_notation.all()
        #music_notation = [get_obj_dictionary(entry, skip_fields) for entry in music_notation_objects]

        #Provenance
        #provenance_objects = instance.ms_provenance.all()
        #provenance = [get_obj_dictionary(entry, skip_fields) for entry in provenance_objects]

        #print('---------------------------------')
        #markers = []
        #for p in provenance_objects:
        #    print(p.place.repository_today_eng)
        #    print(p.place.longitude)
        #    print(p.place.latitude)
        #    markers.append({
        #        'name':p.place.repository_today_eng,
        #        'lon':p.place.longitude,
        #        'lat':p.place.latitude,
        #        })

        #Content
        #content = instance.ms_content.all()


        #Zotero:
        #zotCollection = instance.zoteroCollection
        #if zotCollection is not None:
        #bibliography = instance.ms_bibliography.all()

        #zot = zotero.Zotero(ZOTERO_library_id, ZOTERO_library_type, ZOTERO_api_key)

        #print(zot.key_info())

        #allItems = zot.items()

        #print(allItems)

        #zotItems = []
        #for b in bibliography:
        #    item = zot.item(b.bibliography.zotero_id, limit=50, content='html', style='acm-siggraph', linkwrap='1')
        #    zotItems.append(item[0])


        #zotItems = zot.collection_items(zotCollection, limit=50, content='html', style='acm-siggraph', linkwrap='1')
        #print(zotItems[0])
        #else:
        #    zotItems = ['<p> Empty bibliography </p>']
        
        #return render (request, self.template, {
        #    'manuscript': instance,
        #    'debate': debate,
        #    'info': info, #info_formated
        #    'codicology': codicology,
        #    'layouts': layouts,
        #    'content': content,
        #    'zotero':zotItems,
        #    'music_notation': music_notation,
        #    'provenance': provenance,
        #    'markers': markers
        #    })

def manuscript(request):
    html = '''<html>
        <head>
            <script src="https://cdn.jsdelivr.net/npm/tify@0.29.1/dist/tify.js"></script>
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/tify@0.29.1/dist/tify.css">
        </head>
        <body>
            <div id="tify" style="height: 100%"></div>
            <script>
            new Tify({
            container: '#tify',
            manifestUrl: 'https://api.digitale-sammlungen.de/iiif/presentation/v2/bsb00061148/manifest',
            })
            </script>
        </body>
        <html>'''
    return HttpResponse(html)


class TestPage(Page):
    #create_form = Form.create(auto__model=Manuscripts)
    a_table = Table(auto__model=Content, 
        #query_from_indexes=True,
        columns__manuscript__filter__include=True,
        columns__formula__filter__include=True,
        columns__rubric__filter__include=True,
        columns__rubric_name_from_ms__filter__include=True,
        columns__rubric_sequence__filter__include=True,
        columns__formula_text__filter__include=True,
        columns__where_in_ms_from__filter__include=True,
        columns__where_in_ms_to__filter__include=True,
    )

    class Meta:
        title = 'An iommi Manuscripts page!'

class contentCompareGraph(View):

    def get(self, request, *args, **kwargs):
        left = self.request.GET.get('left')
        right = self.request.GET.get('right')

        ms_ids = [left,right]
        category_column = 'formula_id'
        value_column = 'sequence_in_ms'


        # Query the database for data
        data = []
        idx=0
        for ms_id in ms_ids:
            manuscript = Manuscripts.objects.get(id=ms_id)
            content_objects = Content.objects.filter(manuscript_id=ms_id, formula_id__isnull=False).values(category_column, value_column)
            data.append({'Table': str(manuscript), 'Values': list(content_objects)})
            idx+=1
        
        # Create a DataFrame from the fetched data
        df = pd.DataFrame(data)
        
        # Reshape the DataFrame to have a separate row for each 'formula_id'
        reshaped_data = []

        for index, row in df.iterrows():
            for value_pair in row['Values']:
                print("value_pair: "+str(value_pair))
                reshaped_data.append({'Table': row['Table'], 'formula_id': value_pair['formula_id'], 'sequence_in_ms': value_pair['sequence_in_ms']})

        reshaped_df = pd.DataFrame(reshaped_data)
        
        # Create a Slope Chart
        plt.figure(figsize=(20, 40), dpi=150)
        # Plot the lines connecting the points for the same 'formula_id' from different tables
        unique_formula_ids = reshaped_df['formula_id'].unique()
        
        for formula_id in unique_formula_ids:
            values = reshaped_df[reshaped_df['formula_id'] == formula_id]
            plt.plot(values['Table'], values['sequence_in_ms'], marker='o', label=f'formula_id {formula_id}')
        
        # Add labels and title
        plt.xlabel('Table Name')
        plt.ylabel('sequence_in_ms')
        plt.title('Slope Chart Example')
        
        # Rotate x-axis labels for better readability
        plt.xticks(rotation=45)
        
        # Add a legend
        #plt.legend()
        
        # Save the plot as an image (e.g., PNG format)
        #plt.savefig('static_assets/media/img/'+filename)

        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)

        response = HttpResponse(content_type='image/png')
        
        # Set content of the response using the data from the buffer
        response.write(buf.getvalue())
        
        # Close the buffer to free up resources
        buf.close()
        
        return response

class contentCompareJSON(View):

    def get(self, request, *args, **kwargs):
        left = self.request.GET.get('left')
        right = self.request.GET.get('right')
    
        ms_ids = [left, right]
        category_column = 'formula_id'
        value_column = 'sequence_in_ms'

        # Query the database for data
        data = []
        for ms_id in ms_ids:
            manuscript = Manuscripts.objects.get(id=ms_id)
            content_objects = Content.objects.filter(manuscript_id=ms_id, formula_id__isnull=False)
            data.append({'Table': str(manuscript), 'Values': list(content_objects)})

        # Create a DataFrame from the fetched data
        df = pd.DataFrame(data)

        # Reshape the DataFrame to have a separate row for each 'formula_id'
        reshaped_data = []
        for index, row in df.iterrows():
            for content_object in row['Values']:
                formula_id = content_object.formula_id
                formula = str(content_object.formula)
                rubric_name = content_object.rubric_name_from_ms

                formula_traditions = []
                traditions = content_object.formula.tradition

                for t in traditions.all():
                    formula_traditions.append(t.name)

                reshaped_data.append({
                    'Table': row['Table'],
                    'formula_id': str(formula_id),
                    'sequence_in_ms': content_object.sequence_in_ms,
                    'formula': formula,
                    'rubric_name': rubric_name,
                    'formula_traditions': formula_traditions
                })

        reshaped_df = pd.DataFrame(reshaped_data)

        # Convert the reshaped data to a JSON-friendly format
        json_data = reshaped_df.to_dict(orient='records')

        return JsonResponse(json_data, safe=False)



class contentCompareEditionGraph(View):

    def get(self, request, *args, **kwargs):
        left = self.request.GET.get('left')
        right = self.request.GET.get('right')

        ms_ids = [left,right]
        category_column = 'edition_index'
        value_column = 'rubric_sequence'


        # Query the database for data
        data = []
        for ms_id in ms_ids:
            manuscript = Manuscripts.objects.get(id=ms_id)
            content_objects = Content.objects.filter(manuscript_id=ms_id, edition_index__isnull=False)
            data.append({'Table': str(manuscript), 'Values': list(content_objects)})

        # Create a DataFrame from the fetched data
        df = pd.DataFrame(data)

        # Reshape the DataFrame to have a separate row for each 'edition_index'
        reshaped_data = []

        for index, row in df.iterrows():
            for content_object in row['Values']:
                edition_index = content_object.edition_index # Assuming edition_index is a ForeignKey field in Content model
                reshaped_data.append({'Table': row['Table'], 'edition_index': str(edition_index), 'rubric_sequence': content_object.rubric_sequence})

        reshaped_df = pd.DataFrame(reshaped_data)
        
        # Create a Slope Chart
        plt.figure(figsize=(40, 10), dpi=150)  # Transposing the figure size

        # Plot the lines connecting the points for the same 'edition_index' from different tables
        unique_edition_indexs = reshaped_df['edition_index'].unique()

        for edition_index in unique_edition_indexs:
            values = reshaped_df[reshaped_df['edition_index'] == edition_index]
            line = plt.plot(values['rubric_sequence'], values['Table'], marker='o', label=f'edition_index {str(edition_index)}')  # Swapping x and y axes
            color = line[0].get_color()  # Retrieve the color of the marker used in the line plot
            
            # Annotate only the last point of each edition_index with its label
            # Calculate the midpoint index
            midpoint_index = len(values) // 2
            midpoint = values.iloc[midpoint_index]
            plt.text(midpoint['rubric_sequence'], midpoint['Table'], f'{str(edition_index)}', rotation=33, verticalalignment='top', horizontalalignment='right', fontsize=8, color=color)

        # Add labels and title
        plt.ylabel('Connections')  # Swapping x and y axis labels
        plt.xlabel('rubric_sequence')  # Swapping x and y axis labels
        plt.title('Comparison graph')

        # Rotate y-axis labels for better readability
        plt.yticks(rotation=45)

        # Add a legend
        plt.legend()

        # Save the plot as an image (e.g., PNG format)
        # plt.savefig('static_assets/media/img/'+filename)

        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)

        response = HttpResponse(content_type='image/png')

        # Set content of the response using the data from the buffer
        response.write(buf.getvalue())

        # Close the buffer to free up resources
        buf.close()
        
        return response

import json
from django.http import JsonResponse
from django.views import View
import pandas as pd

class contentCompareEditionJSON(View):

    def get(self, request, *args, **kwargs):
        mss = self.request.GET.get('mss');
        ms_ids = mss.split(';')

        category_column = 'edition_index'
        value_column = 'rubric_sequence'

        # Query the database for data
        data = []
        for ms_id in ms_ids:
            manuscript = Manuscripts.objects.get(id=ms_id)
            content_objects = Content.objects.filter(manuscript_id=ms_id, edition_index__isnull=False)
            data.append({'Table': str(manuscript), 'Values': list(content_objects)})

        # Create a DataFrame from the fetched data
        df = pd.DataFrame(data)

        # Reshape the DataFrame to have a separate row for each 'edition_index'
        reshaped_data = []
        for index, row in df.iterrows():
            for content_object in row['Values']:
                edition_index = content_object.edition_index
                rubric_name_standarized = str(content_object.edition_index.rubric_name_standarized)
                reshaped_data.append({
                    'Table': row['Table'],
                    'edition_index': str(edition_index),
                    'rubric_sequence': content_object.rubric_sequence,
                    'rubric_name_standarized': rubric_name_standarized
                })

        reshaped_df = pd.DataFrame(reshaped_data)

        # Convert the reshaped data to a JSON-friendly format
        json_data = reshaped_df.to_dict(orient='records')

        return JsonResponse(json_data, safe=False)

class MSRitesLookupView(View):
    def get(self, request, *args, **kwargs):
        ms_id = request.GET.get('ms')
        manuscript = get_object_or_404(Manuscripts, id=ms_id)

        print("manuscript = "+str(manuscript))

        # Get all content related to the manuscript with non-empty edition_index and rubric_sequence fields
        ms_content = Content.objects.filter(manuscript=manuscript, edition_index__isnull=False, rubric_sequence__isnull=False)

        sorted_ms_content = ms_content.order_by('rubric_sequence')
        #sorted_ms_content = [str(ms_content.edition_index) for ms_content in sorted_ms_content]


        sorted_unique_ms_content = []
        last_name=''
        for content in sorted_ms_content:
            name = str(content.edition_index)
            if name != last_name:
                sorted_unique_ms_content.append(name)
            last_name=name


        # Initialize dictionary to store similar manuscripts data
        similar_manuscripts = {}

        print("ms_content len = "+str(len(ms_content)))

        all_related_manuscript_ids = {}

        # Iterate through each content entry related to the manuscript
        for content in ms_content:
            # Get all manuscripts related to the current content's edition_index
            related_manuscripts = Manuscripts.objects.filter(ms_content__edition_index=content.edition_index).exclude(id=manuscript.id)

            # Initialize list to store edition_index for current content
            edition_index_list = []

            # Iterate through each related manuscript
            for related_ms in related_manuscripts:
                all_related_manuscript_ids[related_ms.id] = related_ms.id

        # Initialize list to store edition_index for current content
        edition_index_list = []

        # Iterate through each related manuscript
        for related_ms_id in all_related_manuscript_ids:

            related_ms = get_object_or_404(Manuscripts, id=related_ms_id)

            ms_info = {
                'manuscript_id': related_ms.id,
                'manuscript_name': str(related_ms),
                'total_edition_index_count': 0,
                'identical_edition_index_count': 0,
                'identical_edition_index_on_same_sequence_count': 0,
                'identical_edition_index_list': '',
                'edition_index_list': '',
            }

            all_related_content = []

            last_name=''
            for content in ms_content:
                # Get content related to the current related manuscript
                related_content = Content.objects.filter(manuscript=related_ms, edition_index=content.edition_index, rubric_sequence__isnull=False)
                
                if len(related_content)>0:
                    name = str(related_content[0].edition_index)

                    if name != last_name:
                        ms_info['identical_edition_index_list'] += name + ", "
                        ms_info['identical_edition_index_count'] += 1

                        if related_content[0].rubric_sequence == content.rubric_sequence :
                            ms_info['identical_edition_index_on_same_sequence_count'] += 1
                    
                    last_name = name

            # Get sorted list of edition_index for the related manuscript
            all_content = Content.objects.filter(manuscript=related_ms, edition_index__isnull=False, rubric_sequence__isnull=False)
            sorted_edition_index = all_content.order_by('rubric_sequence')#.distinct('edition_index')

            sorted_unique_edition_index = []
            last_name=''
            for content in sorted_edition_index:
                name = str(content.edition_index)
                sequence = content.rubric_sequence

                if name != last_name:
                    sorted_unique_edition_index.append(name)
                last_name=name


            # Append data to edition_index_list
            ms_info['edition_index_list'] = ', '.join(sorted_unique_edition_index)
            ms_info['total_edition_index_count'] = len(sorted_unique_edition_index)
            
            # Add data to similar_manuscripts dictionary
            similar_manuscripts[related_ms.id] = ms_info


        data = {
            'ms_content': sorted_unique_ms_content,
            'similar_ms': similar_manuscripts
        }

        return JsonResponse(data)


class ManuscriptTEIView(View):
    def get(self, request, *args, **kwargs):
        ms_id = request.GET.get('ms')
        manuscript = get_object_or_404(Manuscripts, id=ms_id)
        codicology = manuscript.ms_codicology.first()

        #xml_header = '''<?xml-model href="https://raw.githubusercontent.com/msDesc/consolidated-tei-schema/master/msdesc.rng" type="application/xml" schematypens="http://relaxng.org/ns/structure/1.0"?>
        #<?xml-model href="https://raw.githubusercontent.com/msDesc/consolidated-tei-schema/master/msdesc.rng" type="application/xml" schematypens="http://purl.oclc.org/dsdl/schematron"?>
        #<TEI xmlns="http://www.tei-c.org/ns/1.0" xmlns:tei="http://www.tei-c.org/ns/1.0" xml:id="manuscript_{0}">
        #'''.format(ms_id)


        xml_header = '''<?xml-model href="https://raw.githubusercontent.com/msDesc/consolidated-tei-schema/master/msdesc.rng" type="application/xml" schematypens="http://relaxng.org/ns/structure/1.0"?>
        <?xml-model href="https://raw.githubusercontent.com/msDesc/consolidated-tei-schema/master/msdesc.rng" type="application/xml" schematypens="http://purl.oclc.org/dsdl/schematron"?>
        '''.format(ms_id)

        xml_nsmap = {'tei':'http://www.tei-c.org/ns/1.0'}
        root = Element("TEI", attrib={'xml:id':'manuscript_{0}'.format(ms_id) })
        root.set('xmlns','http://www.tei-c.org/ns/1.0')
        root.set('xmlns:tei','http://www.tei-c.org/ns/1.0')

        #tei_model = '<?xml-model href="https://raw.githubusercontent.com/msDesc/consolidated-tei-schema/master/msdesc.rng" type="application/xml" schematypens="http://purl.oclc.org/dsdl/schematron"?>'
        #root.text = tei_model

        #tei_header = SubElement(root, "teiHeader")
        #tei_header.set("lang", "en")

        file_desc = SubElement(root, "fileDesc")
        title_stmt = SubElement(file_desc, "titleStmt")
        title_element = SubElement(title_stmt, "title")
        title_element.text = str(manuscript.name)

        if manuscript.common_name:
            common_name_element = SubElement(title_stmt, "title", type="collection")
            common_name_element.text = str(manuscript.common_name)

        edition_stmt = SubElement(file_desc, "editionStmt")
        edition_element = SubElement(edition_stmt, "edition")
        edition_element.text = "TEI P5"

        publication_stmt = SubElement(file_desc, "publicationStmt")
        publisher_element = SubElement(publication_stmt, "publisher")
        publisher_element.text = "Special Collections, Bodleian Libraries"

        source_desc = SubElement(file_desc, "sourceDesc")
        ms_desc = SubElement(source_desc, "msDesc", id="manuscript_" + str(ms_id))
        ms_desc.set("lang", "en")

        ms_identifier = SubElement(ms_desc, "msIdentifier")
        shelfmark_element = SubElement(ms_identifier, "idno", type="shelfmark")
        shelfmark_element.text = str(manuscript.shelf_mark)

        title_element = SubElement(ms_desc, "head")
        title_element.text = "Title of the manuscript"

        # Add more elements from the Manuscripts and Codicology models
        if manuscript.dating:
            dating_element = SubElement(ms_desc, "origin")
            orig_date_element = SubElement(dating_element, "origDate")
            orig_date_element.set("calendar", "Gregorian")
            orig_date_element.set("notBefore", str(manuscript.dating.year_from))
            orig_date_element.set("notAfter", str(manuscript.dating.year_to))
            orig_date_element.text = manuscript.dating.time_description

        if manuscript.place_of_origin:
            orig_place_element = SubElement(dating_element, "origPlace")
            country_element = SubElement(orig_place_element, "country")
            country_element.set("key", "place_" + str(manuscript.place_of_origin.id))
            country_element.text = str(manuscript.place_of_origin)


        if codicology:
            phys_desc = SubElement(ms_desc, "physDesc")
            object_desc = SubElement(phys_desc, "objectDesc", form="codex")
            parchment_element = SubElement(object_desc, "supportDesc", material="parch")
            if codicology.number_of_parchment_folios:
                extent_element = SubElement(parchment_element, "extent")
                folios_element = SubElement(extent_element, "measure", type="folios")
                folios_element.text = str(codicology.number_of_parchment_folios)

        # Add more fields from the Codicology model

        xml_content = xml_header + tostring(root, encoding="unicode")  
        return HttpResponse(xml_content, content_type="application/xml")

class ManuscriptTEI(TemplateView):
    template_name = 'manuscript.xml'  # Path to your template

    def get(self, request, *args, **kwargs):
        # Get ms_id from the GET parameters
        ms_id = request.GET.get('ms')

        # Retrieve manuscript from the database or return 404 if not found
        manuscript = get_object_or_404(Manuscripts, id=ms_id)

        medieval_hands = manuscript.ms_hands.filter(is_medieval=True)
        added_hands = manuscript.ms_hands.filter(is_medieval=False)

        # Render the XML template with the manuscript data
        context = self.get_context_data(manuscript=manuscript)
        context['medieval_hands'] = medieval_hands
        context['added_hands'] = added_hands

        xml_content = render_to_string(self.template_name, context)

        # Prepare the response as XML
        response = HttpResponse(xml_content, content_type="application/xml")
        
        #Uncomment for download:
        #response['Content-Disposition'] = f'attachment; filename="manuscript_{ms_id}.xml"'
        response['Content-Disposition'] = 'inline'  # Display inline instead of downloading


        return response

    # Optionally, you can override get_context_data to provide context
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['manuscript'] = kwargs['manuscript']
        return context



class ContentCSVExportView(View):
    def get(self, request, manuscript_id):
        # Check if manuscript_id is valid
        if not (0 < manuscript_id < 99999999):
            return HttpResponse("Invalid manuscript ID.", status=400)

        # Filter Content records based on manuscript_id
        contents = Content.objects.filter(manuscript_id=manuscript_id)

        # Prepare the response as a CSV file
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="content_export.csv"'

        writer = csv.writer(response)
        # Write header
        writer.writerow([
            "id", "manuscript_id", "sequence_in_ms", "formula_id", "formula_text_from_ms",
            "similarity_by_user", "where_in_ms_from", "where_in_ms_to", "rubric_name_from_ms", "digital_page_number", "rubric_id",
            "rubric_sequence_in_the_MS", "original_or_added", "biblical_reference", "reference_to_other_items",
            "edition_index", "comments", "function_id", "subfunction_id", "liturgical_genre_id", "music_notation_id",
            "quire_id", "section_id", "subsection_id", "contributor_id", "entry_date"
        ])

        # Write content rows
        for content in contents:
            writer.writerow([
                content.id,
                content.manuscript_id,
                content.sequence_in_ms,
                content.formula.id if content.formula else "",
                content.formula_text,
                content.similarity_by_user,
                foliation(content.where_in_ms_from),
                foliation(content.where_in_ms_to),
                content.digital_page_number,
                content.rubric_name_from_ms,
                content.rite.id if content.rite else "",
                content.rubric_sequence,
                content.original_or_added,
                content.biblical_reference,
                content.reference_to_other_items,
                str(content.edition_index) if content.edition_index else "",
                content.comments,
                str(content.function) if content.function else "",
                str(content.subfunction) if content.subfunction else "",
                str(content.liturgical_genre) if content.liturgical_genre else "",
                content.music_notation.id if content.music_notation else "",
                content.quire.id if content.quire else "",
                str(content.section) if content.section else "",
                str(content.subsection) if content.subsection else "",
                content.data_contributor.id if content.data_contributor else "",
                content.entry_date,
            ])

        return response



class DeleteContentView(View):
    def delete(self, request, manuscript_id):
        # Check if the user is a superuser
        if not request.user.is_superuser:
            return HttpResponseForbidden("Only superusers can delete content.")

        # Validate manuscript ID
        manuscript = get_object_or_404(Manuscripts, pk=manuscript_id)
        
        # Delete all related content
        deleted_count, _ = Content.objects.filter(manuscript_id=manuscript.id).delete()
        
        return JsonResponse({'status': 'success', 'deleted_count': deleted_count})


class ImproveOurDataFormView(View):
    def post(self, request):
        data = json.loads(request.body)
        name = data.get('name')
        ms_signature = data.get('ms_signature')
        email = data.get('email')
        message = data.get('message')
        captcha = data.get('captcha')
        captcha_key = data.get('captcha_key')

        # Validate captcha
        try:
            stored_captcha = CaptchaStore.objects.get(hashkey=captcha_key)
            if captcha.lower() == stored_captcha.response.lower():
                ImproveOurDataEntry.objects.create(
                    name=name,
                    ms_signature=ms_signature,
                    email=email,
                    message=message
                )
                stored_captcha.delete()
                return JsonResponse({"message": "Thank you! Form submitted successfully.", "success": True})
            else:
                return JsonResponse({"message": "Invalid captcha."}, status=400)
        except CaptchaStore.DoesNotExist:
            return JsonResponse({"message": "Invalid captcha key."}, status=400)

    def get(self, request):
        new_captcha = CaptchaStore.generate_key()
        captcha_image = captcha_image_url(new_captcha)
        return JsonResponse({"captcha_key": new_captcha, "captcha_image": captcha_image})



class DeleteTraditionFromFormulaView(View):
    def delete(self, request, tradition_id):
        # Check if the user is a superuser
        if not request.user.is_superuser:
            return HttpResponseForbidden("Only superusers can delete tradition relations.")

        # Validate tradition ID
        tradition = get_object_or_404(Traditions, pk=tradition_id)
        
        # Delete all relations between this tradition and any formulas
        deleted_count = Formulas.tradition.through.objects.filter(traditions_id=tradition.id).delete()[0]
        
        return JsonResponse({
            'status': 'success',
            'message': f'Removed {deleted_count} relations for tradition {tradition.name}',
            'deleted_count': deleted_count
        })

class AssignMSContentToTraditionView(View):
    def post(self, request, manuscript_id, tradition_id):
        # Check if the user is a superuser
        if not request.user.is_superuser:
            return HttpResponseForbidden("Only superusers can assign content to traditions.")

        # Validate manuscript and tradition
        manuscript = get_object_or_404(Manuscripts, pk=manuscript_id)
        tradition = get_object_or_404(Traditions, pk=tradition_id)
        
        # Get all formulas associated with the manuscript through content
        formulas = Content.objects.filter(
            manuscript_id=manuscript.id,
            formula_id__isnull=False
        ).values_list('formula_id', flat=True).distinct()
        
        # Add relations between formulas and tradition if they don't exist
        added_count = 0
        with transaction.atomic():
            for formula_id in formulas:
                formula = Formulas.objects.get(pk=formula_id)
                if not formula.tradition.filter(id=tradition.id).exists():
                    formula.tradition.add(tradition)
                    added_count += 1
        
        return JsonResponse({
            'status': 'success',
            'message': f'Assigned {added_count} formulas to tradition {tradition.name}',
            'added_count': added_count
        })