# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models
from django.contrib.contenttypes.models import ContentType #dla komentarzy
from django.contrib.contenttypes.fields import GenericForeignKey #dla komentarzy
from django.utils.functional import cached_property
from django.contrib.auth.models import User

from Levenshtein import distance

def toRoman(num):
    if not num:
        return ""

    chlist = "VXLCDM"
    rev = [int(ch) for ch in reversed(str(num))]
    chlist = ["I"] + [chlist[i % len(chlist)] + "\u0304" * (i // len(chlist))
                    for i in range(0, len(rev) * 2)]

    def period(p: int, ten: str, five: str, one: str) -> str:
        if p == 9:
            return one + ten
        elif p >= 5:
            return five + one * (p - 5)
        elif p == 4:
            return one + five
        else:
            return one * p

    return "".join(reversed([period(rev[i], chlist[i * 2 + 2], chlist[i * 2 + 1], chlist[i * 2])
                            for i in range(0, len(rev))]))

#from osm_field.fields import LatitudeField, LongitudeField, OSMField
from django.core.validators import MaxValueValidator, MinValueValidator

class DecorationTypes(models.Model):
    name = models.CharField(max_length=128)
    parent_type = models.ForeignKey("self",models.CASCADE, blank=True, null=True)

    class Meta:
        #managed = False
        db_table = 'decoration_types'
        verbose_name_plural = 'Decoration Types'

    def __str__(self):
        return self.name

class DecorationTechniques(models.Model):
    name = models.CharField(max_length=128)

    class Meta:
        #managed = False
        db_table = 'decoration_techniques'
        verbose_name_plural = 'Decoration Techniques'

    def __str__(self):
        return self.name

class Characteristics(models.Model):
    name = models.CharField(max_length=128)

    class Meta:
        #managed = False
        db_table = 'characteristics'
        verbose_name_plural = 'Characteristics'

    def __str__(self):
        return self.name

class Subjects(models.Model):
    name = models.CharField(max_length=128)

    class Meta:
        #managed = False
        db_table = 'subjects'
        verbose_name_plural = 'Subjects'

    def __str__(self):
        return self.name

class Colours(models.Model):
    name = models.CharField(max_length=128)
    rgb = models.CharField(max_length=8, blank=True, null=True)
    
    parent_colour = models.ForeignKey("self",models.CASCADE, blank=True, null=True)


    class Meta:
        #managed = False
        db_table = 'colours'
        verbose_name_plural = 'Colours'

    def __str__(self):
        return self.name

class FeastRanks(models.Model):
    name = models.CharField(max_length=128)

    class Meta:
        #managed = False
        db_table = 'feast_ranks'
        verbose_name_plural = 'Feast Ranks'

    def __str__(self):
        return self.name

#[ ] TODO Where in MS where_in_ms_from change to folio_starting
#[ ] TODO Uwzględnić  verbose name przy wyświetlaniu w view
class Calendar(models.Model):
    manuscript = models.ForeignKey('Manuscripts', models.DO_NOTHING, related_name='ms_calendar')
    where_in_ms_from = models.DecimalField(max_digits=5, decimal_places=1)
    where_in_ms_to = models.DecimalField(max_digits=5, decimal_places=1)

    #folio_starting = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    #folio_ending = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    #pagination_from = models.IntegerField( null=True, blank=True)
    #pagination_to = models.IntegerField(null=True, blank=True)

    rite_name_standarized = models.ForeignKey('RiteNames', models.DO_NOTHING, null=True, blank=True)
    content = models.ForeignKey('Content', models.DO_NOTHING, related_name='calendar_content',verbose_name="Content (if present)", null=True, blank=True)

    month = models.IntegerField( null=True, blank=True)
    day = models.IntegerField( null=True, blank=True)
    latin_name = models.CharField(max_length=128,verbose_name="Latin name of the date from ms")
    feast_name = models.CharField(max_length=128,verbose_name="feast name")

    feast_rank = models.ForeignKey('FeastRanks', models.DO_NOTHING, related_name='calendar_feast',verbose_name="Rank of the feast")

    rubricated = models.BooleanField(null=True, blank=True)
    littera_dominicalis = models.CharField(max_length=2)
    aureus_numerus = models.IntegerField( null=True, blank=True)

    readonly_fields = ('aureus_numerus_roman',)
    aureus_numerus_roman = models.CharField(max_length=20, blank=True, null=True)

    other_remarks = models.CharField(max_length=128,verbose_name="other remarks from ms", null=True, blank=True)
    original = models.BooleanField(null=True, blank=True)

    date_of_the_addition = models.ForeignKey('TimeReference', models.DO_NOTHING, related_name='calendar_addition_dating', blank=True, null=True)

    comments = models.TextField(blank=True, null=True)

    entry_date = models.DateTimeField(auto_now=True)
    authors = models.ManyToManyField('Contributors', related_name='%(class)s_authors', blank=True)
    data_contributor = models.ForeignKey('Contributors', models.DO_NOTHING, related_name='%(class)s_contributors', null=True, blank=True)

    def save(self, *args, **kwargs):
        # Update the aureus_numerus_roman field before saving
        self.aureus_numerus_roman = toRoman(self.aureus_numerus)  # Adjust this based on your logic

        super().save(*args, **kwargs)


    class Meta:
        #managed = False
        db_table = 'calendar'
        verbose_name_plural = 'Calendar'

    def __str__(self):
        return self.latin_name

class DecorationSubjects(models.Model):
    decoration = models.ForeignKey('Decoration', models.DO_NOTHING, related_name='decoration_subjects')
    subject = models.ForeignKey('Subjects', models.DO_NOTHING, related_name='decoration_subject')

    class Meta:
        #managed = False
        db_table = 'decoration_subjects'
        verbose_name_plural = 'Decoration Subjects'

    def __str__(self):
        return str(self.decoration) +" / "+ str(self.subject)


class DecorationColours(models.Model):
    decoration = models.ForeignKey('Decoration', models.DO_NOTHING, related_name='decoration_colours')
    colour = models.ForeignKey('Colours', models.DO_NOTHING, related_name='decoration_colour')

    class Meta:
        #managed = False
        db_table = 'decoration_colours'
        verbose_name_plural = 'Decoration Colours'

    def __str__(self):
        return str(self.decoration) +" / "+ str(self.colour)

class DecorationCharacteristics(models.Model):
    decoration = models.ForeignKey('Decoration', models.DO_NOTHING, related_name='decoration_characteristics')
    characteristics = models.ForeignKey('Characteristics', models.DO_NOTHING, related_name='decoration_characteristics')

    class Meta:
        #managed = False
        db_table = 'decoration_characteristics'
        verbose_name_plural = 'Decoration characteristics'

    def __str__(self):
        return str(self.decoration) +" / "+ str(self.characteristics)

class Decoration(models.Model):
    manuscript = models.ForeignKey('Manuscripts', models.DO_NOTHING, related_name='ms_decorations')
    original_or_added = models.CharField(max_length=10,choices=[("ORIGINAL", "original"),("ADDED", "added")], blank=True, null=True)
    date_of_the_addition = models.ForeignKey('TimeReference', models.DO_NOTHING, related_name='decoration_dating', blank=True, null=True)

    content = models.ForeignKey('Content', models.SET_NULL, related_name='content_decoration', blank=True, null=True)
    calendar = models.ForeignKey('Calendar', models.DO_NOTHING, related_name='calendar_decoration', blank=True, null=True)

    where_in_ms_from = models.DecimalField(max_digits=5, decimal_places=1)
    where_in_ms_to = models.DecimalField(max_digits=5, decimal_places=1)
    location_on_the_page = models.CharField(max_length=10,choices=[("WITHIN", "within the column"),("MARGIN", "on the margin"),("IN_TEXT", "in the text line")], blank=True, null=True)

    decoration_type = models.ForeignKey('DecorationTypes', models.DO_NOTHING, related_name='decoration_type')
    decoration_subtype = models.ForeignKey('DecorationTypes', models.DO_NOTHING, related_name='decoration_subtype',blank=True, null=True)

    size_characteristic = models.CharField(max_length=10,choices=[("SMALL", "small"),("1LINE", "1-line"),("2LINES", "2-lines"),("3LINES", "3-lines"),("1SYSTEM", "1-system"),("2SYSTEMS", "2-systems"),("LARGE", "large"),("FULL", "full page")], blank=True, null=True)
    size_height_min = models.PositiveIntegerField(blank=True, null=True)
    size_height_max = models.PositiveIntegerField(blank=True, null=True)

    size_width_min = models.PositiveIntegerField(blank=True, null=True)
    size_width_max = models.PositiveIntegerField(blank=True, null=True)
    
    #decoration_colour = models.ForeignKey('Colours', models.DO_NOTHING, related_name='decoration_colour', blank=True, null=True)

    monochrome_or_colour = models.CharField(max_length=2,choices=[("M", "monochromatic"),("B", "bicolored"),("C", "multicolored")], blank=True, null=True)

    #characteristic = models.ForeignKey('Characteristics', models.DO_NOTHING, related_name='decoration_characteristic', blank=True, null=True)
    technique = models.ForeignKey('DecorationTechniques', models.DO_NOTHING, related_name='decoration_technique', blank=True, null=True)

    #subject = models.ForeignKey('Subjects', models.DO_NOTHING, related_name='decoration_subject')
    ornamented_text = models.CharField(max_length=128, blank=True, null=True)

    rite_name_standarized = models.ForeignKey('RiteNames', models.DO_NOTHING, null=True, blank=True)

    comments = models.TextField(blank=True, null=True)

    entry_date = models.DateTimeField(auto_now=True)
    authors = models.ManyToManyField('Contributors', related_name='%(class)s_authors', blank=True)
    data_contributor = models.ForeignKey('Contributors', models.DO_NOTHING, related_name='%(class)s_contributors', null=True, blank=True)


    class Meta:
        #managed = False
        db_table = 'decoration'
        verbose_name_plural = 'Decoration'

    def __str__(self):
        name = ""
        if self.manuscript:
            name += str(self.manuscript)
        name += " ("+str(self.where_in_ms_from)+")"
        return name

class ManuscriptBibliography(models.Model):
    bibliography = models.ForeignKey('Bibliography', models.DO_NOTHING)
    manuscript = models.ForeignKey('Manuscripts', models.DO_NOTHING, related_name='ms_bibliography')

    class Meta:
        #managed = False
        db_table = 'manuscript_bibliography'
        verbose_name_plural = 'Manuscript Bibliography'

    def __str__(self):
        name = ""
        if self.manuscript:
            name += str(self.manuscript)
        if self.bibliography:
            name += " / "+ str(self.bibliography)
        return name

class Bibliography(models.Model):
    title = models.CharField(max_length=128)
    author = models.CharField(max_length=128,blank=True, null=True)
    shortname = models.CharField(max_length=5,blank=True, null=True)
    year = models.IntegerField(blank=True, null=True)
    zotero_id = models.CharField(max_length=128,blank=True, null=True)
    hierarchy = models.IntegerField(blank=True, null=True)

    class Meta:
        #managed = False
        db_table = 'bibliography'
        verbose_name_plural = 'Bibliography'

    def __str__(self):
        return self.title

class AttributeDebate(models.Model):
    text = models.CharField(max_length=256)
    timestamp = models.DateTimeField(auto_now_add=True)

    bibliography = models.ForeignKey('Bibliography', models.DO_NOTHING)

    #Odwołanie do konkretnego wpisu dowolnego modelu:
    #(typ modelu):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    #(object_id):
    object_id = models.PositiveIntegerField()
    #To pole ułatwia pracę z obiektami poprzez bezpośrednie odwołanie:
    content_object = GenericForeignKey('content_type', 'object_id')

    # Pole do przechowywania nazwy pola komentowanego:
    field_name = models.CharField(max_length=255) 

    class Meta:
        #managed = False
        db_table = 'attribute_debate'
        verbose_name_plural = 'Attribute Debate'

    def __str__(self):
        return str(self.field_name) + self.text + ' by '+ str(self.bibliography)

class Condition(models.Model):
    manuscript = models.ForeignKey('Manuscripts', models.DO_NOTHING, related_name='ms_condition')
    damage = models.CharField(max_length=10,choices=[("very", "very damaged"),("average", "average damaged"),("slightly","slightly damaged")], blank=True, null=True)

    parchment_shrinkage = models.BooleanField(null=True)
    illegible_text = models.BooleanField(null=True)
    ink_corrosion = models.BooleanField(null=True)
    copper_corrosion = models.BooleanField(null=True)
    powdering_or_cracking_paint_layer = models.BooleanField(null=True)
    conservation = models.BooleanField(null=True)
    conservation_date = models.ForeignKey('TimeReference', models.DO_NOTHING, related_name='%(class)s_conservation_dating', null=True, blank=True)
    darkening = models.BooleanField(null=True)
    water_staining = models.BooleanField(null=True)
    historic_repairs = models.BooleanField(null=True)

    comments = models.TextField(blank=True, null=True)

    entry_date = models.DateTimeField(auto_now=True)
    authors = models.ManyToManyField('Contributors', related_name='%(class)s_authors', blank=True)
    data_contributor = models.ForeignKey('Contributors', models.DO_NOTHING, related_name='%(class)s_contributors', null=True, blank=True)

    class Meta:
        #managed = False
        db_table = 'condition'
        verbose_name_plural = 'Condition'

    def __str__(self):
        return str(self.manuscript) + ' (condition)'

class EditionContent(models.Model):
    bibliography = models.ForeignKey('Bibliography', models.DO_NOTHING)
    formula = models.ForeignKey('Formulas', models.DO_NOTHING, blank=True, null=True)
    rite_name_standarized = models.ForeignKey('RiteNames', models.DO_NOTHING, null=True, blank=True)
    feast_rite_sequence = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    subsequence = models.PositiveIntegerField( null=True, blank=True)
    page = models.PositiveIntegerField( null=True, blank=True)
    function = models.ForeignKey('ContentFunctions', models.DO_NOTHING, related_name='%(class)s_main_function',  blank=True, null=True)
    subfunction = models.ForeignKey('ContentFunctions', models.DO_NOTHING, related_name='%(class)s_sub_function',  blank=True, null=True)
    
    entry_date = models.DateTimeField(auto_now=True)
    authors = models.ManyToManyField('Contributors', related_name='%(class)s_authors', blank=True)
    data_contributor = models.ForeignKey('Contributors', models.DO_NOTHING, related_name='%(class)s_contributors', null=True, blank=True)

    #filled_automatically:
    #formula_text_standarized


    def __str__(self):
        #Weź pierwsze z bibliografii i jeśli ma ma skrót to skrót + 'c.' wtedy chapter/subsequence i 'p.' wtedy page
        txt = str(self.bibliography)
        if hasattr(self.bibliography , 'shortname'):
            txt = self.bibliography.shortname

        if self.feast_rite_sequence is not None:
            txt += ' c.'+str(self.feast_rite_sequence)
            if self.subsequence is not None:
                txt += '/'+str(self.subsequence)

        if self.page is not None:
            txt += ' p.'+str(self.page)

        return txt



class Sections(models.Model):
    name = models.CharField(max_length=128)
    parent_section = models.ForeignKey("self",models.CASCADE, blank=True, null=True)

    class Meta:
        #managed = False
        db_table = 'sections'
        verbose_name_plural = 'Sections'

    def __str__(self):
        return self.name

class ContentFunctions(models.Model):
    name = models.CharField(max_length=128)
    parent_function = models.ForeignKey("self",models.CASCADE, blank=True, null=True)

    class Meta:
        #managed = False
        db_table = 'content_functions'
        verbose_name_plural = 'Content functions'

    def __str__(self):
        return self.name

class Contributors(models.Model):
    initials = models.CharField(max_length=4)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    affiliation = models.CharField(max_length=100,null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    url = models.URLField(null=True, blank=True)

    class Meta:
        db_table = 'contributors'
        verbose_name_plural = 'Contributors'

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

"""
class Authors(models.Model):
    initials = models.CharField(max_length=4)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    affiliation = models.CharField(max_length=100,null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    url = models.URLField(null=True, blank=True)

    class Meta:
        db_table = 'authors'
        verbose_name_plural = 'Authors'

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
"""

class UserOpenAIAPIKey(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    api_key = models.CharField(max_length=100)

    class Meta:
        db_table = 'user_openai_api_key'
        verbose_name_plural = 'Users OpenAI API Keys'

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    edit_mode = models.BooleanField(default=False)

class Content(models.Model):

    def calc_last_sequence():
        # Znajdź maksymalną wartość 'pole_liczbowe' wśród wszystkich obiektów tego samego typu
        max_value = Content.objects.aggregate(max_value=models.Max('sequence_in_ms'))['max_value']
        # Sprawdź, czy max_value istnieje (bazie danych jest co najmniej jeden rekord)
        # i zwróć wartość o 1 większą niż maksymalna wartość
        if max_value is not None:
            return max_value + 1
        else:
            return 1  # Jeśli nie ma rekordów, zwróć 1 jako wartość domyślną

    manuscript = models.ForeignKey('Manuscripts', models.DO_NOTHING, related_name='ms_content')
    formula = models.ForeignKey('Formulas', models.DO_NOTHING, blank=True, null=True)
    rite = models.ForeignKey('RiteNames', models.DO_NOTHING, blank=True, null=True)
    rite_name_from_ms = models.CharField(max_length=1024, null=True, blank=True)
    subrite_name_from_ms = models.TextField(null=True, blank=True)
    rite_sequence = models.PositiveIntegerField(null=True, blank=True, default=calc_last_sequence)

    formula_text = models.TextField(null=True, blank=True)
    #folio_starting = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    #folio_ending = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    #pagination_from = models.IntegerField( null=True, blank=True)
    #pagination_to = models.IntegerField(null=True, blank=True)
    sequence_in_ms = models.PositiveIntegerField(null=True, blank=True, default=calc_last_sequence)
    where_in_ms_from = models.CharField(max_length=32, default="")
    where_in_ms_to = models.CharField(max_length=32, null=True, blank=True, default="")
    digital_page_number = models.PositiveIntegerField(null=True, blank=True)

    original_or_added = models.CharField(max_length=10,choices=[("ORIGINAL", "original"),("ADDED", "added")], blank=True, null=True)
    
    liturgical_genre = models.ForeignKey('LiturgicalGenres', models.DO_NOTHING, blank=True, null=True, related_name='content_genres')
    quire = models.ForeignKey('Quires', models.DO_NOTHING, blank=True, null=True)
    section = models.ForeignKey('Sections', models.DO_NOTHING, related_name='%(class)s_main_section',  blank=True, null=True)
    subsection = models.ForeignKey('Sections', models.DO_NOTHING, related_name='%(class)s_sub_section',  blank=True, null=True)
    music_notation = models.ForeignKey('ManuscriptMusicNotations', models.DO_NOTHING, blank=True, null=True)
    function = models.ForeignKey('ContentFunctions', models.DO_NOTHING, related_name='%(class)s_main_function',  blank=True, null=True)
    subfunction = models.ForeignKey('ContentFunctions', models.DO_NOTHING, related_name='%(class)s_sub_function',  blank=True, null=True)
    biblical_reference = models.CharField(max_length=31, null=True, blank=True)
    reference_to_other_items = models.CharField(max_length=127, null=True, blank=True)
    similarity_by_user = models.CharField(max_length=4,choices=[("0", "the formula not in the editions"),("0.5", "paraphrase"),("1", "exact match")], blank=True, null=True)
    proper_texts = models.BooleanField(null=True, blank=True)

    similarity_levenshtein = models.FloatField(null=True, blank=True)  # Add a field to store similarity
    similarity_levenshtein_percent = models.FloatField(null=True, blank=True)  # Add a field to store similarity


    entry_date = models.DateTimeField(auto_now=True)
    authors = models.ManyToManyField('Contributors', related_name='%(class)s_authors', blank=True)
    data_contributor = models.ForeignKey('Contributors', models.DO_NOTHING, related_name='%(class)s_contributors', null=True, blank=True)

    #filled_automatically:
    #formula_text_standarized

    edition_index = models.ForeignKey('EditionContent', models.DO_NOTHING, related_name='%(class)s_edition_index',  blank=True, null=True)
    edition_subindex = models.CharField(max_length=1024, null=True, blank=True)
    
    comments = models.TextField(blank=True, null=True)

    #New columns inspired by USUARIUM project:
    #text_standarization_id = models.CharField(max_length=32, null=True, blank=True)
    layer = models.ForeignKey('Layer', models.DO_NOTHING, blank=True, null=True)

    mass_hour = models.ForeignKey('MassHour', models.DO_NOTHING, related_name='%(class)s_mass_hour', blank=True, null=True)
    genre = models.ForeignKey('Genre', models.DO_NOTHING, related_name='%(class)s_genre', blank=True, null=True)
    season_month = models.ForeignKey('SeasonMonth', models.DO_NOTHING, related_name='%(class)s_season_month', blank=True, null=True)
    week = models.ForeignKey('Week', models.DO_NOTHING, related_name='%(class)s_week', blank=True, null=True)
    day = models.ForeignKey('Day', models.DO_NOTHING, related_name='%(class)s_day', blank=True, null=True)


    def calculate_and_save_similarity(self):
        # Calculate similarity and save to the field
        s1 = self.formula.text if self.formula else ''
        s2 = self.formula_text or ''

        #dyftongi
        s1.replace('oe','e')
        s2.replace('oe','e')

        s1.replace('ae','e')
        s2.replace('ae','e')

        s1.replace('y','i')
        s2.replace('y','i')
        

        similarity_levenshtein = distance(s1, s2, weights=(1, 1, 1))

        if self.similarity_levenshtein != similarity_levenshtein:
            self.similarity_levenshtein = similarity_levenshtein
            max_length = max(len(s1), len(s2))
            if max_length != 0:
                self.similarity_levenshtein_percent = 100.0*(1- (self.similarity_levenshtein / max_length))
            else:
                self.similarity_levenshtein_percent = None
                
            self.save(update_fields=['similarity_levenshtein','similarity_levenshtein_percent'])  # Save only the similarity field

    def save(self, *args, **kwargs):
        # Call the superclass's save() method to save the object
        super(Content, self).save(*args, **kwargs)
        
        # Calculate and save similarity after saving the object
        self.calculate_and_save_similarity()


    class Meta:
        #managed = False
        db_table = 'content'
        verbose_name_plural = 'Content'

    def __str__(self):
        txt = self.formula_text
        if txt is None:
            return "noname"
        if len(txt)>30:
            txt = txt[0:30]
            txt += '(...)'
        return txt

class TimeReference(models.Model):
    time_description = models.CharField(max_length=64)
    century_from = models.IntegerField()
    century_to = models.IntegerField()
    year_from = models.IntegerField()
    year_to = models.IntegerField()

    class Meta:
        #managed = False
        db_table = 'time_reference'
        verbose_name_plural = 'Time References'

    def __str__(self):
        txt = self.time_description
        if txt is None:
            return "noname"
        if len(txt)>30:
            txt = txt[0:30]
            txt += '(...)'
        return txt

class LiturgicalGenres(models.Model):
    title = models.CharField(max_length=128)

    class Meta:
        #managed = False
        db_table = 'liturgical_genres'
        verbose_name_plural = 'Liturgical Genres'

    def __str__(self):
        txt = self.title
        if txt is None:
            return "noname"
        if len(txt)>30:
            txt = txt[0:30]
            txt += '(...)'
        return txt

#it is like alternative names for genres
class LiturgicalGenresNames(models.Model):
    genre = models.ForeignKey(LiturgicalGenres, models.DO_NOTHING)
    title = models.CharField(max_length=128)

    class Meta:
        #managed = False
        db_table = 'liturgical_genres_names'
        verbose_name_plural = 'Liturgical Genres Names'

    def __str__(self):
        txt = self.title
        if txt is None:
            return "noname"
        if len(txt)>30:
            txt = txt[0:30]
            txt += '(...)'
        return txt

class Places(models.Model):
    longitude = models.FloatField(validators=[MinValueValidator(-180.0), MaxValueValidator(180.0)], blank=True, null=True)
    latitude = models.FloatField(validators=[MinValueValidator(-90.0), MaxValueValidator(90.0)], blank=True, null=True)

    place_type = models.CharField(max_length=10,choices=[("library", "library"),("center", "center"),("scriptory","scriptory"),("multiple","multiple")], blank=True, null=True)

    country_today_eng = models.CharField(max_length=64, blank=True, null=True)
    region_today_eng = models.CharField(max_length=64, blank=True, null=True)
    city_today_eng = models.CharField(max_length=64, blank=True, null=True)
    repository_today_eng = models.CharField(max_length=255, blank=True, null=True)

    country_today_local_language = models.CharField(max_length=64, blank=True, null=True)
    region_today_local_language = models.CharField(max_length=64, blank=True, null=True)
    city_today_local_language = models.CharField(max_length=64, blank=True, null=True)
    repository_today_local_language = models.CharField(max_length=255, blank=True, null=True)

    country_historic_eng = models.CharField(max_length=64, blank=True, null=True)
    region_historic_eng = models.CharField(max_length=64, blank=True, null=True)
    city_historic_eng = models.CharField(max_length=64, blank=True, null=True)
    repository_historic_eng = models.CharField(max_length=255, blank=True, null=True)

    country_historic_local_language = models.CharField(max_length=64, blank=True, null=True)
    region_historic_local_language = models.CharField(max_length=64, blank=True, null=True)
    city_historic_local_language = models.CharField(max_length=64, blank=True, null=True)
    repository_historic_local_language = models.CharField(max_length=255, blank=True, null=True)

    country_historic_latin = models.CharField(max_length=64, blank=True, null=True)
    region_historic_latin = models.CharField(max_length=64, blank=True, null=True)
    city_historic_latin = models.CharField(max_length=64, blank=True, null=True)
    repository_historic_latin = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        #managed = False
        db_table = 'places'
        verbose_name_plural = 'Places'

    def __str__(self):
        txt = ''

        if self.country_today_eng is not None:
            txt += self.country_today_eng

        if self.city_today_eng is not None:
            if txt is not None:
                txt += ", "
            txt += self.city_today_eng
        
        if self.repository_today_eng is not None:
            if txt is not None:
                txt += ", "
            txt += self.repository_today_eng

        if txt is None or len(txt)<3:
            txt = self.repository_today_local_language

            if txt is None or len(txt)<3:
                txt = self.repository_historic_eng
            if txt is None or len(txt)<3:
                txt = self.repository_historic_local_language
            if txt is None or len(txt)<3:
                txt = self.repository_historic_latin

            if txt is None or len(txt)<3:
                txt = self.city_today_eng
                if txt is None or len(txt)<3:
                    txt = self.city_today_local_language
                if txt is None or len(txt)<3:
                    txt = self.city_historic_eng
                if txt is None or len(txt)<3:
                    txt = self.city_historic_local_language
                if txt is None or len(txt)<3:
                    txt = self.city_historic_latin

                if txt is None or len(txt)<3:
                    txt = self.region_today_eng
                if txt is None or len(txt)<3:
                    txt = self.region_today_local_language

        if txt is None:
            return "noname"
        if len(txt)>256:
            txt = txt[0:256]
            txt += '(...)'
        return txt
    
class ScriptNames(models.Model):
    name = models.CharField(max_length=128)

    class Meta:
        #managed = False
        db_table = 'names'
        verbose_name_plural = 'Script Names'

    def __str__(self):
        txt = self.name
        if txt is None:
            return "noname"

        return txt

class ImproveOurDataEntry(models.Model):
    name = models.CharField(max_length=1024)
    ms_signature = models.CharField(max_length=1024)
    email = models.EmailField(max_length=1024, blank=True, null=True)
    message = models.TextField()

    changes_made = models.BooleanField(null=True, default=False)
    checked_by = models.ForeignKey('Contributors', models.DO_NOTHING, related_name='%(class)s_checked_by', null=True, blank=True)
    entry_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.ms_signature


class Manuscripts(models.Model):
    name = models.CharField(max_length=255)
    rism_id = models.CharField(max_length=255, blank=True, null=True)
    foreign_id = models.CharField(max_length=255, blank=True, null=True)
    contemporary_repository_place = models.ForeignKey(Places, models.DO_NOTHING, blank=True, null=True)
    shelf_mark = models.CharField(max_length=255, blank=True, null=True)
    usuarium_shelfmark = models.CharField(max_length=255, blank=True, null=True)
    liturgical_genre_comment = models.TextField(blank=True, null=True)
    common_name = models.CharField(max_length=255, blank=True, null=True)
    dating = models.ForeignKey(TimeReference, models.DO_NOTHING, related_name='%(class)s_dating', blank=True, null=True)
    dating_comment = models.TextField(blank=True, null=True)
    place_of_origin = models.ForeignKey(Places, models.DO_NOTHING, related_name='%(class)s_origin', blank=True, null=True)
    place_of_origin_comment = models.TextField(blank=True, null=True)
    #number_of_parchment_folios = models.IntegerField(blank=True, null=True)
    #number_of_paper_leaves = models.IntegerField(blank=True, null=True)
    #page_size_max_height = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    #page_size_max_width = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    #parchment_thickness = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    main_script = models.ForeignKey(ScriptNames, models.DO_NOTHING, blank=True, null=True)
    how_many_columns_mostly = models.PositiveIntegerField(blank=True, null=True)
    lines_per_page_usually = models.PositiveIntegerField(blank=True, null=True)
    how_many_quires = models.PositiveIntegerField(blank=True, null=True)
    quires_comment = models.TextField(blank=True, null=True)
    foliation_or_pagination = models.CharField(max_length=12,choices=[("FOLIATION", "FOLIATION"),("PAGINATION", "PAGINATION")], blank=True, null=True)
    decorated = models.BooleanField(null=True)
    decoration_comments = models.TextField(blank=True, null=True)
    music_notation = models.BooleanField(null=True)
    music_notation_comments = models.TextField(blank=True, null=True)
    binding_date = models.ForeignKey(TimeReference, models.DO_NOTHING, related_name='%(class)s_binding_date', blank=True, null=True)
    binding_place = models.ForeignKey(Places, models.DO_NOTHING, related_name='%(class)s_binding_place', blank=True, null=True)
    links = models.CharField(max_length=1024, blank=True, null=True)

    additional_url = models.CharField(max_length=1024, null=True, blank=True)
    iiif_manifest_url = models.CharField(max_length=1024, blank=True, null=True)
    #zoteroCollection = models.CharField(max_length=64, blank=True, null=True)
    image = models.ImageField(upload_to='images/', blank=True, null=True)
    pdf_url = models.CharField(max_length=1024, blank=True, null=True)

    general_comment = models.TextField(blank=True, null=True)
    form_of_an_item = models.CharField(max_length=2,choices=[("C", "CODEX"),("F", "FRAGMENT"),("P", "PALIMPSEST"),("L", "LOST ITEM")], blank=True, null=True)

    connected_ms = models.TextField(blank=True, null=True)
    where_in_connected_ms = models.TextField(blank=True, null=True)

    display_as_main = models.BooleanField(null=True)

    entry_date = models.DateTimeField(auto_now=True)
    authors = models.ManyToManyField('Contributors', related_name='%(class)s_authors', blank=True)
    data_contributor = models.ForeignKey('Contributors', models.DO_NOTHING, related_name='%(class)s_contributors', null=True, blank=True)

    #rites = models.OneToOneField('Rites', on_delete=models.CASCADE)
    #rites = models.ForeignKey('Rites', models.DO_NOTHING, related_name='+')

    class Meta:
        #managed = False
        db_table = 'manuscripts'
        verbose_name_plural = 'Manuscripts'

    def __str__(self):
        txt = self.name
        if self.rism_id:
            txt = self.rism_id + ' ' + self.name

        if txt is None:
            return "noname"
        if len(txt)>60:
            txt = txt[0:60]
            txt += '(...)'
        return txt

    def get_material(self):
        """
        FOR TEI 
        Determines the material type for the manuscript based on all Quires.
        Returns 'chart' if all are paper, 'perg' if all are parchment, and 'mixed' otherwise.
        """
        quire_materials = self.ms_quires.values_list('material', flat=True)

        if all(material == 'paper' for material in quire_materials):
            return 'chart'  # All paper
        elif all(material == 'parchment' for material in quire_materials):
            return 'perg'  # All parchment
        else:
            return 'mixed'  # Mixed materials

class Projects(models.Model):
    name = models.CharField(max_length=64, default="Project Name")

    class Meta:
        #managed = False
        verbose_name_plural = 'Projects'

    def __str__(self): 
        return self.name


class MSProjects(models.Model):
    manuscript = models.ForeignKey(Manuscripts, models.DO_NOTHING, related_name='ms_projects')
    project = models.ForeignKey(Projects, models.DO_NOTHING)

    class Meta:
        #managed = False
        verbose_name_plural = 'Manuscript Projects'

class Clla(models.Model):
    manuscript = models.ForeignKey(Manuscripts, models.DO_NOTHING, related_name='ms_clla')

    clla_no = models.CharField(max_length=255, blank=True, null=True)
    liturgical_genre = models.CharField(max_length=512, blank=True, null=True)
    dating = models.ForeignKey(TimeReference, models.DO_NOTHING, related_name='%(class)s_dating', blank=True, null=True)
    dating_comment = models.TextField(blank=True, null=True)
    #provenance = models.ForeignKey(Places, models.DO_NOTHING, related_name='%(class)s_provenance', blank=True, null=True)
    provenance = models.CharField(max_length=512, blank=True, null=True)
    provenance_comment = models.TextField(blank=True, null=True)
    comment = models.TextField(blank=True, null=True)

    authors = models.CharField(max_length=128, blank=True, default="Klaus Gamber", null=True)
    data_contributor  = models.CharField(max_length=512, default="Quirin Rosenberger", blank=True, null=True)


    class Meta:
        #managed = False
        verbose_name_plural = 'CLLA'

    def __str__(self): 
        txt = str(self.clla_no)
        if txt is None:
            return "noname"
        return txt

class Layouts(models.Model):
    manuscript = models.ForeignKey(Manuscripts, models.DO_NOTHING, related_name='ms_layouts')
    name = models.CharField(max_length=32, blank=True, null=True)
    where_in_ms_from = models.DecimalField(max_digits=5, decimal_places=1)
    where_in_ms_to = models.DecimalField(max_digits=5, decimal_places=1)
    how_many_columns = models.PositiveIntegerField(blank=True, null=True)
    lines_per_page_maximum = models.PositiveIntegerField(blank=True, null=True)
    lines_per_page_minimum = models.PositiveIntegerField(blank=True, null=True)
    written_space_height_max = models.PositiveIntegerField(blank=True, null=True)
    written_space_width_max = models.PositiveIntegerField(blank=True, null=True)
    #https://manual.mmfc.be/p/MMFC:Lists/Layout_characteristics
    ruling_method = models.CharField(max_length=16,choices=[("blind-point", "blind-point"),("board", "board"),("ink", "ink"),("lead-point", "lead-point"),("rake", "rake"),("rake-lead", "rake (lead-point)"),("rake-ink", "rake (ink)"),("rake-lead-ink", "rake (lead-point and ink)")], blank=True, null=True)
    written_above_the_top_line = models.BooleanField(null=True)
    pricking = models.CharField(max_length=10,choices=[("yes", "yes"),("no", "no"),("partially", "partially")], blank=True, null=True)
    distance_between_horizontal_ruling = models.CharField(max_length=255, blank=True, null=True)
    distance_between_vertical_ruling = models.CharField(max_length=255, blank=True, null=True)


    layout_links = models.CharField(max_length=1024, blank=True, null=True)
    graph_img = models.ImageField(upload_to='images/', blank=True, null=True)

    comments = models.TextField(blank=True, null=True)


    entry_date = models.DateTimeField(auto_now=True)
    authors = models.ManyToManyField('Contributors', related_name='%(class)s_authors', blank=True)
    data_contributor = models.ForeignKey('Contributors', models.DO_NOTHING, related_name='%(class)s_contributors', null=True, blank=True)

    class Meta:
        #managed = False
        db_table = 'layouts'
        verbose_name_plural = 'Layouts'

    def __str__(self): 
        txt = str(self.manuscript) +" (" + str(self.id) + ")"
        if txt is None:
            return "noname"
        if len(txt)>30:
            txt = txt[0:30]
            txt += '(...)'
        return txt

class Codicology(models.Model):
    manuscript = models.ForeignKey(Manuscripts, on_delete=models.CASCADE, related_name='ms_codicology')
    
    #should be visible in main manuscript description too:
    number_of_parchment_folios = models.IntegerField(blank=True, null=True)
    number_of_paper_leaves = models.IntegerField(blank=True, null=True)
    page_size_max_height = models.PositiveIntegerField(blank=True, null=True)
    page_size_max_width = models.PositiveIntegerField(blank=True, null=True)
    parchment_thickness_min = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    parchment_thickness_max = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)

    #based on https://scribes.lochac.sca.org/articles/parchment.htm
    parchment_colour = models.ForeignKey('Colours', models.DO_NOTHING, related_name='parchment_colour',blank=True, null=True)

    #models.CharField(max_length=12,choices=[("white", "white"),("purple", "purple"),("indigo", "indigo"),("green", "green"),("red", "red"),("peach", "peach")], blank=True, null=True)
    parchment_comment = models.TextField(blank=True, null=True)
    paper_size_max_height = models.PositiveIntegerField(blank=True, null=True)
    paper_size_max_width = models.PositiveIntegerField(blank=True, null=True)
    watermarks = models.BooleanField(null=True)
    foliation_comment = models.TextField(blank=True, null=True)
    #layout and layout links visible in visualization:
    #layout_links = models.CharField(max_length=1024, blank=True, null=True)

    entry_date = models.DateTimeField(auto_now=True)
    authors = models.ManyToManyField('Contributors', related_name='%(class)s_authors', blank=True)
    data_contributor = models.ForeignKey('Contributors', models.DO_NOTHING, related_name='%(class)s_contributors', null=True, blank=True)


    class Meta:
        #managed = False
        db_table = 'codicology'
        verbose_name_plural = 'Codicology and Paleography'

    def __str__(self): 
        txt = str(self.manuscript)
        if txt is None:
            return "noname"
        if len(txt)>30:
            txt = txt[0:30]
            txt += '(...)'
        return txt


class Quires(models.Model):
    manuscript = models.ForeignKey(Manuscripts, models.DO_NOTHING, related_name='ms_quires')

    sequence_of_the_quire = models.PositiveIntegerField()
    #http://leksykon.oprawoznawczy.ukw.edu.pl/index.php/Sk%C5%82adka
    type_of_the_quire = models.CharField(max_length=12,choices=[("bifolium", "bifolium"),("binion", "binion"),("ternion", "ternion"),("quaternion", "quaternion"),("quinternion", "quinternion"),("seksternion", "seksternion"),("septernion", "septernion"),("okternion", "okternion")])
    where_in_ms_from = models.DecimalField(max_digits=5, decimal_places=1)
    where_in_ms_to = models.DecimalField(max_digits=5, decimal_places=1)
    graph_img = models.ImageField(upload_to='images/', blank=True, null=True)
    material = models.CharField(max_length=10,choices=[("parchment", "parchment"),("paper", "paper quire")], blank=True, null=True)

    comment = models.TextField(blank=True, null=True)
    
    entry_date = models.DateTimeField(auto_now=True)
    authors = models.ManyToManyField('Contributors', related_name='%(class)s_authors', blank=True)
    data_contributor = models.ForeignKey('Contributors', models.DO_NOTHING, related_name='%(class)s_contributors', null=True, blank=True)

    class Meta:
        #managed = False
        db_table = 'quires'
        verbose_name_plural = 'Quires'

    def __str__(self): 
        txt = str(self.manuscript) + ' ('+ str(self.sequence_of_the_quire) + ')'
        if txt is None:
            return "noname"
        if len(txt)>30:
            txt = txt[0:30]
            txt += '(...)'
        return txt


class Watermarks(models.Model):
    name = models.CharField(max_length=255)
    external_id = models.IntegerField(blank=True, null=True)
    watermark_img = models.ImageField(upload_to='images/', blank=True, null=True)
    comment = models.TextField(blank=True, null=True)

    entry_date = models.DateTimeField(auto_now=True)
    authors = models.ManyToManyField('Contributors', related_name='%(class)s_authors', blank=True)
    data_contributor = models.ForeignKey('Contributors', models.DO_NOTHING, related_name='%(class)s_contributors', null=True, blank=True)

    class Meta:
        #managed = False
        db_table = 'watermarks'
        verbose_name_plural = 'Watermarks'

    def __str__(self): 
        txt = self.name
        if txt is None:
            return "noname"
        if len(txt)>30:
            txt = txt[0:30]
            txt += '(...)'
        return txt

class MusicNotationNames(models.Model):
    name = models.CharField(max_length=50)

    class Meta:
        #managed = False
        db_table = 'music_notation_names'
        verbose_name_plural = 'Music Notation Names'

    def __str__(self): 
        txt = self.name
        if txt is None:
            return "noname"
        if len(txt)>30:
            txt = txt[0:30]
            txt += '(...)'
        return txt 

class ManuscriptMusicNotations(models.Model):
    manuscript = models.ForeignKey(Manuscripts, models.DO_NOTHING, related_name='ms_music_notation')

    music_notation_name = models.ForeignKey(MusicNotationNames, models.DO_NOTHING)
    sequence_in_ms = models.PositiveIntegerField()
    where_in_ms_from = models.DecimalField(max_digits=5, decimal_places=1)
    where_in_ms_to = models.DecimalField(max_digits=5, decimal_places=1)
    dating = models.ForeignKey(TimeReference, models.DO_NOTHING, blank=True, null=True)
    original = models.BooleanField(null=True)
    on_lines = models.BooleanField(null=True)
    music_custos = models.BooleanField(null=True)
    number_of_lines = models.PositiveIntegerField(blank=True,null=True)
    comment = models.TextField(blank=True, null=True)

    entry_date = models.DateTimeField(auto_now=True)
    authors = models.ManyToManyField('Contributors', related_name='%(class)s_authors', blank=True)
    data_contributor = models.ForeignKey('Contributors', models.DO_NOTHING, related_name='%(class)s_contributors', null=True, blank=True)

    class Meta:
        #managed = False
        db_table = 'manuscript_music_notations'
        verbose_name_plural = 'Manuscript Music Notations'

    def __str__(self): 
        txt = str(self.manuscript) + ' / ' + str(self.music_notation_name)
        if txt is None:
            return "noname"
        if len(txt)>30:
            txt = txt[0:30]
            txt += '(...)'
        return txt 


class Origins(models.Model):
    manuscript = models.ForeignKey(Manuscripts, models.DO_NOTHING, related_name='ms_origins')

    origins_date = models.ForeignKey(TimeReference, models.DO_NOTHING, blank=True, null=True)
    origins_place = models.ForeignKey(Places, models.DO_NOTHING, null=True)
    origins_comment = models.TextField(blank=True, null=True)
    provenance_comments = models.TextField(blank=True, null=True)

    entry_date = models.DateTimeField(auto_now=True)
    authors = models.ManyToManyField('Contributors', related_name='%(class)s_authors', blank=True)
    data_contributor = models.ForeignKey('Contributors', models.DO_NOTHING, related_name='%(class)s_contributors', null=True, blank=True)

    class Meta:
        #managed = False
        db_table = 'origins'
        verbose_name_plural = 'Origins and Datings'

    def __str__(self): 
        txt = str(self.manuscript) + ' / ' + str(self.origins_date) + ' / ' + str(self.origins_place)
        return txt 


class Provenance(models.Model):
    #MANUSCRIPT ID	DATE FROM	DATE TO	PLACE	TIMELINE SEQUENCE	COMMENTS
    manuscript = models.ForeignKey(Manuscripts, models.DO_NOTHING, related_name='ms_provenance')

    date_from = models.ForeignKey(TimeReference, models.DO_NOTHING, blank=True, null=True, related_name='provenance_from')
    date_to = models.ForeignKey(TimeReference, models.DO_NOTHING, blank=True, null=True, related_name='provenance_to')
    
    place = models.ForeignKey(Places, models.DO_NOTHING, null=True)

    timeline_sequence = models.PositiveIntegerField()

    comment = models.TextField(blank=True, null=True)

    entry_date = models.DateTimeField(auto_now=True)
    authors = models.ManyToManyField('Contributors', related_name='%(class)s_authors', blank=True)
    data_contributor = models.ForeignKey('Contributors', models.DO_NOTHING, related_name='%(class)s_contributors', null=True, blank=True)

    class Meta:
        #managed = False
        db_table = 'provenance'
        verbose_name_plural = 'Provenance'

    def __str__(self): 
        txt = str(self.manuscript) + ' / ' + str(self.date_from) + '-' + str(self.date_to) + ' / ' + str(self.place)
        return txt 

class BindingTypes(models.Model):
    name = models.CharField(max_length=64) 

    class Meta:
        db_table = 'binding_types'
        verbose_name_plural = 'Binding Types'

    def __str__(self): 
        return self.name

class BindingStyles(models.Model):
    name = models.CharField(max_length=64) 

    class Meta:
        db_table = 'binding_styles'
        verbose_name_plural = 'Binding Styles'

    def __str__(self): 
        return self.name
#######
class BindingMaterials(models.Model):
    name = models.CharField(max_length=64) 

    class Meta:
        db_table = 'binding_materials'
        verbose_name_plural = 'Binding Materials'

    def __str__(self): 
        return self.name

# []TODO sprawdzić wszędzie gdzie jest models czy nie warto zrobić CASCADE! 
class ManuscriptBindingMaterials(models.Model):
    manuscript = models.ForeignKey(Manuscripts, models.DO_NOTHING, related_name='ms_binding_materials')
    material = models.ForeignKey(BindingMaterials, models.CASCADE)

    class Meta:
        db_table = 'manuscript_binding_materials'
        verbose_name_plural = 'Manuscript Binding Materials'

    def __str__(self): 
        return str(self.manuscript)  + '/' + str(self.material)


class BindingDecorationTypes(models.Model):
    name = models.CharField(max_length=64) 

    class Meta:
        db_table = 'binding_decoration_types'
        verbose_name_plural = 'Binding Decoration Types'

    def __str__(self): 
        return self.name

class ManuscriptBindingDecorations(models.Model):
    manuscript = models.ForeignKey(Manuscripts, models.DO_NOTHING, related_name='ms_binding_decorations')
    decoration = models.ForeignKey(BindingDecorationTypes, models.CASCADE)

    class Meta:
        db_table = 'manuscript_binding_decorations'
        verbose_name_plural = 'Manuscript Binding Decorations'

    def __str__(self): 
        return str(self.manuscript)  + '/' + str(self.decoration)

class BindingComponents(models.Model):
    name = models.CharField(max_length=64) 

    class Meta:
        db_table = 'binding_components'
        verbose_name_plural = 'Binding Components'

    def __str__(self): 
        return self.name

class ManuscriptBindingComponents(models.Model):
    manuscript = models.ForeignKey(Manuscripts, models.DO_NOTHING, related_name='ms_binding_components')
    component = models.ForeignKey(BindingComponents, models.CASCADE)

    class Meta:
        db_table = 'manuscript_binding_components'
        verbose_name_plural = 'Manuscript Binding Components'

    def __str__(self): 
        return str(self.manuscript)  + '/' + str(self.component)

class Binding(models.Model):
    manuscript = models.ForeignKey(Manuscripts, models.DO_NOTHING, related_name='ms_binding')

    max_height = models.PositiveIntegerField(blank=True, null=True)
    max_width = models.PositiveIntegerField(blank=True, null=True)
    block_max = models.PositiveIntegerField(blank=True, null=True)
    date = models.ForeignKey(TimeReference, models.DO_NOTHING, blank=True, null=True)
    place_of_origin = models.ForeignKey(Places, models.DO_NOTHING, blank=True, null=True)
    type_of_binding = models.ForeignKey(BindingTypes, models.DO_NOTHING, null=True)
    style_of_binding = models.ForeignKey(BindingStyles, models.DO_NOTHING, null=True)
    category = models.CharField(max_length=12,choices=[("original", "original"),("early", "early modern"),("historical", "Historical rebinding"),("conservation", "Conservation binding"),("restored", "Restored binding")], blank=True, null=True)

    #materials #many-to-one
    #type of decoration #many-to-one
    decoration_comment = models.TextField(blank=True, null=True)
    general_comments = models.TextField(blank=True, null=True)
    characteristic_of_components = models.TextField(blank=True, null=True)

    #MANUSCRIPT ID		TYPE OF BINDING	STYLE OF BINDING
    #DECORATION COMMENT	GENERAL COMMENTS

    entry_date = models.DateTimeField(auto_now=True)
    authors = models.ManyToManyField('Contributors', related_name='%(class)s_authors', blank=True)
    data_contributor = models.ForeignKey('Contributors', models.DO_NOTHING, related_name='%(class)s_contributors', null=True, blank=True)

    class Meta:
        #managed = False
        db_table = 'bindings'
        verbose_name_plural = 'Bindings'

    def __str__(self): 
        txt = str(self.manuscript) + ' binding ' + str(self.id)
        return txt 


class Hands(models.Model):
    rism = models.CharField(max_length=50,blank=True, null=True)
    dating = models.ForeignKey(TimeReference, models.DO_NOTHING, blank=True, null=True)
    name = models.CharField(max_length=64,blank=True, null=True)
    is_identified = models.BooleanField(null=True)

    class Meta:
        db_table = 'hands'
        verbose_name_plural = 'Hands'

    def __str__(self): 
        txt = self.name
        if txt is None:
            return "noname"
        if len(txt)>30:
            txt = txt[0:30]
            txt += '(...)'
        return txt


class ManuscriptHands(models.Model):
    manuscript = models.ForeignKey(Manuscripts, models.DO_NOTHING, related_name='ms_hands')

    hand = models.ForeignKey(Hands, models.DO_NOTHING)
    script_name = models.ForeignKey(ScriptNames, models.DO_NOTHING)
    hand_name_in_ms = models.CharField(max_length=255, blank=True, null=True)
    sequence_in_ms = models.PositiveIntegerField()
    where_in_ms_from = models.DecimalField(max_digits=5, decimal_places=1, blank=True, null=True)
    where_in_ms_to = models.DecimalField(max_digits=5, decimal_places=1, blank=True, null=True)
    is_range_interrupted = models.BooleanField(default=False)
    is_medieval = models.BooleanField(null=True)
    is_main_text = models.BooleanField(null=True)
    dating = models.ForeignKey(TimeReference, models.DO_NOTHING, blank=True, null=True)

    comment = models.TextField(blank=True, null=True)

    entry_date = models.DateTimeField(auto_now=True)
    authors = models.ManyToManyField('Contributors', related_name='%(class)s_authors', blank=True)
    data_contributor = models.ForeignKey('Contributors', models.DO_NOTHING, related_name='%(class)s_contributors', null=True, blank=True)

    class Meta:
        db_table = 'manuscript_hands'
        verbose_name_plural = 'Manuscript Hands'

    def __str__(self): 
        txt = str(self.manuscript) + ' / ' + str(self.hand)+ ' / ' + str(self.sequence_in_ms)
        if txt is None:
            return "noname"
        if len(txt)>30:
            txt = txt[0:30]
            txt += '(...)'
        return txt

class ManuscriptWatermarks(models.Model):
    manuscript = models.ForeignKey(Manuscripts, models.DO_NOTHING, related_name='ms_watermarks')

    watermark = models.ForeignKey(Watermarks, models.DO_NOTHING)
    where_in_manuscript = models.CharField(max_length=255)

    class Meta:
        #managed = False
        db_table = 'manuscript_watermarks'
        verbose_name_plural = 'Manuscript Watermarks'

    def __str__(self): 
        txt = str(self.manuscript) + ' / ' + str(self.watermark)
        if txt is None:
            return "noname"
        if len(txt)>30:
            txt = txt[0:30]
            txt += '(...)'
        return txt


class Traditions(models.Model):
    name = models.CharField(max_length=100)
    color_rgb = models.CharField(max_length=8, blank=True, null=True)
    genre = models.ForeignKey(LiturgicalGenres, models.DO_NOTHING, blank=True, null=True)

    class Meta:
        db_table = 'traditions'
        verbose_name_plural = 'Traditions'

    def __str__(self): 
        return self.name

class Formulas(models.Model):
    co_no = models.CharField(max_length=50)
    text = models.TextField(blank=True, null=True)
    tradition = models.ManyToManyField('Traditions', related_name='%(class)s_traditions', blank=True)
    translation_en = models.TextField(blank=True, null=True)
    translation_pl = models.TextField(blank=True, null=True)


    class Meta:
        #managed = False
        db_table = 'formulas'
        verbose_name_plural = 'Formulas'

    def __str__(self): 
        txt = self.text
        if txt is None:
            return "noname"
        #if len(txt)>90:
        #    txt = txt[0:90]
        #    txt += '(...)'
        return txt


class ManuscriptGenres(models.Model):
    manuscript = models.ForeignKey(Manuscripts, models.DO_NOTHING, related_name='ms_genres')

    genre = models.ForeignKey(LiturgicalGenres, models.DO_NOTHING)

    class Meta:
        #managed = False
        db_table = 'manuscript_genres'
        verbose_name_plural = 'Manuscript Genres'

    def __str__(self):
        txt = str(self.manuscript) + ' to '+ str(self.genre)
        if txt is None:
            return "noname"
        if len(txt)>30:
            txt = txt[0:30]
            txt += '(...)'
        return txt

class RiteNames(models.Model):

    name = models.CharField(max_length=128, unique=True)
    english_translation = models.CharField(max_length=128,  blank=True, null=True)
    section = models.ForeignKey('Sections', models.DO_NOTHING,  blank=True, null=True)
    votive = models.BooleanField(null=True)
    ceremony = models.ForeignKey('Ceremony', models.DO_NOTHING,  blank=True, null=True)

    class Meta:
        #managed = False
        db_table = 'rite_names'
        verbose_name_plural = 'Rite Names Standarized'

    def __str__(self):
        return self.name



"""
class Rites(models.Model):
    manuscript = models.ForeignKey(Manuscripts, models.DO_NOTHING, related_name='ms_rites')
    rite_name_standarized = models.ForeignKey(RiteNames, models.DO_NOTHING, null=True, blank=True)
    rite_sequence = models.IntegerField() #feast/rite
    rubric_name_from_ms = models.CharField(max_length=255, null=True, blank=True)
    proper_texts = models.BooleanField(null=True, blank=True)

    entry_date = models.DateTimeField(auto_now=True)
    authors = models.ManyToManyField('Contributors', related_name='%(class)s_authors', blank=True)
    data_contributor = models.ForeignKey('Contributors', models.DO_NOTHING, related_name='%(class)s_contributors', null=True, blank=True)

    #To inherit from formulas:
    #folio_starting
    #folio_ending
    #pagination_starting
    #pagination_ending
    #original_or_added = models.IntegerField(blank=True, null=True)

    #delete:
    #century = models.IntegerField(blank=True, null=True)
    #ceremony_date_id = models.DateField(blank=True, null=True)
    #ceremony_id = models.IntegerField(blank=True, null=True)
    #ceremony_date_name = models.IntegerField(blank=True, null=True)

    class Meta:
        #managed = False
        db_table = 'rites'
        verbose_name_plural = 'Rites'

    def __str__(self):
        txt = self.rubric_name_from_ms
        if txt is None:
            return "noname"
        if len(txt)>30:
            txt = txt[0:30]
            txt += '(...)'
        return txt
"""

### NOWE from USUARIUM ###

# Column A
class Type(models.Model):
    short_name = models.CharField(max_length=8, unique=True)#max 28
    name = models.CharField(max_length=16, unique=True)#max 65

    def __str__(self):
        return "("+self.short_name + ") " + self.name

    class Meta:
        #managed = False
        db_table = 'type'
        verbose_name_plural = 'Types'


# Column C
class SeasonMonth(models.Model):
    short_name = models.CharField(max_length=4, unique=True)#max 28
    name = models.CharField(max_length=30, unique=True)#max 65
    kind = models.CharField(max_length=12,choices=[("S", "season"),("M", "month")], blank=True, null=True)
    types = models.ManyToManyField('Type', related_name='%(class)s_types', blank=True)


    def __str__(self):
        season_or_month = '['+self.kind+']'
        return season_or_month+" ("+ self.short_name + ") " + self.name

    class Meta:
        #managed = False
        db_table = 'season_month'
        verbose_name_plural = 'Seasons/Months'

# Column D
class Week(models.Model):
    short_name = models.CharField(max_length=4, unique=True)#max 28
    name = models.CharField(max_length=75, unique=True)#max 65
    types = models.ManyToManyField('Type', related_name='%(class)s_types', blank=True)

    def __str__(self):
        return self.short_name + " " + self.name

    class Meta:
        #managed = False
        db_table = 'week'
        verbose_name_plural = 'Weeks'

# Column E
class Day(models.Model):
    part = models.CharField(max_length=2,choices=[("T", "temporal"),("S", "sanctoral")], blank=True, null=True)
    short_name = models.CharField(max_length=4, unique=True)#max 28
    name = models.CharField(max_length=65, unique=True)#max 65
    types = models.ManyToManyField('Type', related_name='%(class)s_types', blank=True)

    def __str__(self):
        return self.short_name + " " + self.name

    class Meta:
        #managed = False
        db_table = 'day'
        verbose_name_plural = 'Days'


# Column H
class MassHour(models.Model):
    short_name = models.CharField(max_length=4, unique=True)#max 28
    name = models.CharField(max_length=80, unique=True)#max 65
    type = models.ForeignKey('Type', models.DO_NOTHING, blank=True, null=True)

    def __str__(self):
        return self.short_name + " " + self.name

    class Meta:
        #managed = False
        db_table = 'mass_hour'
        verbose_name_plural = 'Mass/Hours'

# Column L
class Layer(models.Model):
    short_name = models.CharField(max_length=4, unique=True)#max 28
    name = models.CharField(max_length=30, unique=True)#max 65

    def __str__(self):
        return self.short_name + " " + self.name

    class Meta:
        #managed = False
        db_table = 'layer'
        verbose_name_plural = 'Layers'

# Column I
class Genre(models.Model):
    short_name = models.CharField(max_length=28, unique=True)#max 28
    name = models.CharField(max_length=100, unique=True)#max 65
    types = models.ManyToManyField('Type', related_name='%(class)s_types', blank=True)
    layers = models.ManyToManyField('Layer', related_name='%(class)s_layers', blank=True)

    def __str__(self):
        return "("+self.short_name + ") " + self.name

    class Meta:
        #managed = False
        db_table = 'genre'
        verbose_name_plural = 'Genres'


class Topic(models.Model):
    name = models.CharField(max_length=64, blank=True, null=True)
    section = models.ForeignKey('Sections', models.DO_NOTHING,  blank=True, null=True) #oryginalne kind
    votive = models.BooleanField(null=True)
    parent = models.ForeignKey("self",models.CASCADE, blank=True, null=True)

    def __str__(self):
        return self.name or "Unnamed Topic"

    class Meta:
        db_table = 'topic'
        verbose_name = "Topic"
        verbose_name_plural = "Topics"

# Column I
class Ceremony(models.Model):
    name = models.CharField(max_length=40, blank=True, null=True)
    latin_keywords = models.CharField(max_length=400, blank=True)
    short_description = models.TextField(blank=True)

    def __str__(self):
        return self.name or "Unnamed Ceremony"

    class Meta:
        db_table = 'ceremony'
        verbose_name = "Ceremony"
        verbose_name_plural = "Ceremonies"


class ContentTopic(models.Model):
    content = models.ForeignKey('Content', models.CASCADE, related_name='content_topics')
    topic = models.ForeignKey('Topic', models.CASCADE, related_name='topic_contents')

    def __str__(self):
        return f"{self.content} - {self.topic}"

    class Meta:
        db_table = 'content_topics'
        verbose_name = "Content Topic"
        verbose_name_plural = "Content Topics"


class TextStandarization(models.Model):
    usu_id = models.CharField(max_length=10, blank=True, null=True)
    cantus_id = models.CharField(max_length=10, blank=True, null=True)
    co_no = models.CharField(max_length=10, blank=True, null=True)
    formula = models.ForeignKey(Formulas, models.DO_NOTHING, blank=True, null=True)

    standard_incipit = models.CharField(max_length=64, blank=True, null=True)
    standard_full_text = models.TextField(blank=True, null=True)
    