from openai import OpenAI
import re #for extracting sql
from django.core.cache import cache
from django.contrib.auth.models import User
from .models import UserOpenAIAPIKey, Manuscripts


def get_all_manuscript_names(projectId):
    queryset = Manuscripts.objects.all()

    #print("projectId = " + str(projectId))
    if projectId != 0:
        queryset = queryset.filter(ms_projects__project__id=projectId)

    # Start with headers
    csv_data = '"id","name","rism_id","foreign_id","shelf_mark"\n'

    # Iterate over the queryset to create CSV rows
    for manuscript in queryset:
        row = f'"{manuscript.id}","{manuscript.name}","{manuscript.rism_id or ""}","{manuscript.foreign_id or ""}","{manuscript.shelf_mark or ""}"\n'
        csv_data += row

    #print('csv names:')
    #print(csv_data)

    return csv_data


# TODO dodać spowrotem, gdy będą wypełnione:
"""
"places","country_today_local_language","varchar"
"places","region_today_local_language","varchar"
"places","city_today_local_language","varchar"
"places","repository_today_local_language","varchar"
"places","country_historic_eng","varchar"
"places","region_historic_eng","varchar"
"places","city_historic_eng","varchar"
"places","repository_historic_eng","varchar"
"places","country_historic_local_language","varchar"
"places","region_historic_local_language","varchar"
"places","city_historic_local_language","varchar"
"places","repository_historic_local_language","varchar"
"places","country_historic_latin","varchar"
"places","region_historic_latin","varchar"
"places","city_historic_latin","varchar"
"places","repository_historic_latin","varchar"
"""
        

def get_or_create_assistant(user_api_key,projectId):
    # Check if the assistant is already cached
    assistant = cache.get(f'assistant_{user_api_key}')
    if assistant is None:
        print("Creating new assistant")
        # If not cached, create a new assistant and cache it
        client = OpenAI(api_key=user_api_key)
        assistant = client.beta.assistants.create(
            name="Ritus SQL Assistant",
            instructions=
"""
I will provide you the database structure as a csv below.. Then i will ask you some questions. Respond ONLY with SQL code. You can add comments, but only as SQL comments (starting from --). You cannot write anything but SQL code with comments.
Make sure that you will use table names and column names only from the structure below.
If user asks you question about some objects, please ALWAYS include the NAME of the objects too (if available in the schema) .
Include a name, even if the user doesn't specifically ask for it.
Always include both name and id.
If you include id, include name too.
Answer in the same language that user used.
Always use the MySQL syntax.

If you don't understand or the question is ambiguous, please use SQL comment (starting from  "--" ) to tell user how he can be more precise and what is unclear for you.
If you cannot answer - please use the SQL comment to tell why.

You can write only SELECT statements. You cannot write INSERT, DROP, DELETE or any other queries.

Please write only ONE complete SELECT statement.
Do not explain the steps.

ALWAYS wrap the table names and the column names in backticks ( ` )!

About the data:
If user asks about number with suffix 'r' - change that suffix to '.1' and change suffix 'v' to '.2' as decimal point.
If some tables has field where_in_ms_from or where_in_ms_to - you can join those tables using this data and manuscript_id even if they do not have direct foreign keys. 

This is the db structure:
  
"Table","Column","Type","Comment (optional)"
"attribute_debate","id","bigint"
"attribute_debate","text","varchar"
"attribute_debate","timestamp","datetime"
"attribute_debate","object_id","int"
"attribute_debate","field_name","varchar"
"attribute_debate","bibliography_id","bigint"
"attribute_debate","content_type_id","int"
"bibliography","id","bigint"
"bibliography","title","varchar"
"bibliography","author","varchar"
"bibliography","shortname","varchar"
"bibliography","year","int"
"bibliography","zotero_id","varchar"
"bibliography","hierarchy","int"
"binding_decoration_types","id","bigint"
"binding_decoration_types","name","varchar"
"binding_materials","id","bigint"
"binding_materials","name","varchar"
"binding_styles","id","bigint"
"binding_styles","name","varchar"
"binding_types","id","bigint"
"binding_types","name","varchar"
"calendar","id","bigint"
"calendar","where_in_ms_from","decimal"
"calendar","where_in_ms_to","decimal"
"calendar","month","int"
"calendar","day","int"
"calendar","latin_name","varchar"
"calendar","feast_name","varchar"
"calendar","rubricated","tinyint"
"calendar","littera_dominicalis","varchar"
"calendar","aureus_numerus","int"
"calendar","other_remarks","varchar"
"calendar","original","tinyint"
"calendar","comments","longtext"
"calendar","entry_date","datetime"
"calendar","content_id","bigint"
"calendar","data_contributor_id","bigint"
"calendar","date_of_the_addition_id","bigint",foreign key to time_reference table
"calendar","feast_rank_id","bigint"
"calendar","manuscript_id","bigint"
"calendar","rite_name_standarized_id","bigint"
"calendar","aureus_numerus_roman","varchar"
"codicology","id","bigint"
"codicology","number_of_parchment_folios","int"
"codicology","number_of_paper_leaves","int"
"codicology","page_size_max_height","int"
"codicology","page_size_max_width","int"
"codicology","parchment_thickness_max","decimal"
"codicology","parchment_comment","longtext"
"codicology","paper_size_max_height","int"
"codicology","paper_size_max_width","int"
"codicology","watermarks","tinyint"
"codicology","foliation_comment","longtext"
"codicology","entry_date","datetime"
"codicology","data_contributor_id","bigint"
"codicology","manuscript_id","bigint"
"codicology","parchment_colour_id","bigint"
"codicology","parchment_thickness_min","decimal"
"layouts","id","bigint"
"layouts","where_in_ms_from","decimal"
"layouts","where_in_ms_to","decimal"
"layouts","how_many_columns","int"
"layouts","lines_per_page_maximum","int"
"layouts","lines_per_page_minimum","int"
"layouts","written_space_height_max","int"
"layouts","written_space_width_max","int"
"layouts","ruling_method","varchar", can be "blind-point","board","ink""lead-point","rake","rake-lead","rake-ink","rake-lead-ink"
"layouts","written_above_the_top_line","tinyint"
"layouts","pricking","varchar", can be "yes", "no", "partially"
"layouts","layout_links","varchar"
"layouts","graph_img","varchar"
"layouts","entry_date","datetime"
"layouts","data_contributor_id","bigint"
"layouts","manuscript_id","bigint"
"layouts","comments","longtext"
"layouts","name","varchar"
"layouts","distance_between_horizontal_ruling","varchar"
"layouts","distance_between_vertical_ruling","varchar"
"colours","id","bigint"
"colours","name","varchar", can be: creamy,copper,gray,gold,silver,brown,rose,purple,cyan,orange,yellow,black,white,blue,green,red
"colours","rgb","varchar"
"condition","id","bigint"
"condition","damage","varchar", can be "very" if very damaged, "average" or "slightly" or null
"condition","parchment_shrinkage","tinyint"
"condition","illegible_text","tinyint"
"condition","ink_corrosion","tinyint"
"condition","copper_corrosion","tinyint"
"condition","powdering_or_cracking_paint_layer","tinyint"
"condition","conservation","tinyint"
"condition","entry_date","datetime"
"condition","conservation_date_id","bigint",foreign key to time_reference table
"condition","data_contributor_id","bigint"
"condition","manuscript_id","bigint"
"condition","comments","longtext"
"indexerapp_projects","id","bigint"
"indexerapp_projects","name","varchar"
"content_functions","id","bigint"
"content_functions","name","varchar"
"content_functions","parent_function_id","bigint"
"contributors","id","bigint"
"contributors","initials","varchar"
"contributors","first_name","varchar"
"contributors","last_name","varchar"
"contributors","affiliation","varchar"
"contributors","email","varchar"
"contributors","url","varchar"
"decoration","id","bigint"
"decoration","original_or_added","varchar", can be: "ORIGINAL" or "ADDED"
"decoration","where_in_ms_from","decimal"
"decoration","where_in_ms_to","decimal"
"decoration","location_on_the_page","varchar", can be: "WITHIN" meaning "within the column"), ("MARGIN" meaning "on the margin"),("IN_TEXT" meaning "in the text line")
"decoration","size_characteristic","varchar", can be: [("SMALL" meaning "small"),("1LINE" meaning "1-line"),("2LINES" meaning "2-lines"),("3LINES" meaning "3-lines"),("1SYSTEM" meaning "1-system"),("2SYSTEMS" meaning "2-systems"),("LARGE" meaning "large"),("FULL" meaning "full page")]
"decoration","size_height","int"
"decoration","size_width","int"
"decoration","monochrome_or_colour","varchar", can be "M" if monochromatic, "B" if bicolored, or "C" if multicolored
"decoration","comments","longtext"
"decoration","entry_date","datetime"
"decoration","calendar_id","bigint"
"decoration","characteristic_id","bigint"
"decoration","content_id","bigint"
"decoration","data_contributor_id","bigint"
"decoration","date_of_the_addition_id","bigint",foreign key to time_reference table
"decoration","decoration_subtype_id","bigint"
"decoration","decoration_type_id","bigint"
"decoration","manuscript_id","bigint"
"decoration","rite_name_standarized_id","bigint"
"decoration","technique_id","bigint"
"decoration","ornamented_text","varchar"
"provenance","id","bigint"
"provenance","timeline_sequence","int",does represent sequence of events
"provenance","comment","longtext"
"provenance","entry_date","datetime"
"provenance","data_contributor_id","bigint"
"provenance","date_from_id","bigint",foreign key to time_reference table
"provenance","date_to_id","bigint",foreign key to time_reference table
"provenance","manuscript_id","bigint"
"provenance","place_id","bigint"
"decoration_characteristics","id","bigint"
"decoration_characteristics","name","varchar"
"decoration_subjects","id","bigint"
"decoration_subjects","decoration_id","bigint"
"decoration_subjects","subject_id","bigint"
"decoration_techniques","id","bigint"
"decoration_techniques","name","varchar"
"decoration_types","id","bigint"
"decoration_types","name","varchar"
"decoration_types","parent_type_id","bigint"
"decoration_colours","id","bigint"
"decoration_colours","colour_id","bigint", colours foreign key
"decoration_colours","decoration_id","bigint", decoration foreign key
"feast_ranks","id","bigint"
"feast_ranks","name","varchar"
"formulas","id","bigint"
"formulas","co_no","varchar"
"formulas","text","longtext"
"hands","id","bigint"
"hands","rism","varchar"
"hands","name","varchar"
"hands","dating_id","bigint"
"liturgical_genres","id","bigint"
"liturgical_genres","title","varchar", can be: "Graduale", "Benedictional", "Ritual", "Calendar", "Collectar", "Pontifical", "Missal", "Sacramentary" 
"liturgical_genres_names","id","bigint"
"liturgical_genres_names","title","varchar"
"liturgical_genres_names","genre_id","bigint"
"manuscript_bibliography","id","bigint"
"manuscript_bibliography","bibliography_id","bigint"
"manuscript_bibliography","manuscript_id","bigint"
"manuscript_binding_decorations","id","bigint"
"manuscript_binding_decorations","decoration_id","bigint"
"manuscript_binding_decorations","manuscript_id","bigint"
"manuscript_binding_materials","id","bigint"
"manuscript_binding_materials","manuscript_id","bigint"
"manuscript_binding_materials","material_id","bigint"
"manuscript_genres","id","bigint"
"manuscript_genres","genre_id","bigint"
"manuscript_genres","manuscript_id","bigint"
"manuscript_hands","id","bigint"
"manuscript_hands","sequence_in_ms","int"
"manuscript_hands","where_in_ms_from","decimal"
"manuscript_hands","where_in_ms_to","decimal"
"manuscript_hands","is_medieval","tinyint"
"manuscript_hands","is_main_text","tinyint"
"manuscript_hands","comment","longtext"
"manuscript_hands","entry_date","datetime"
"manuscript_hands","data_contributor_id","bigint"
"manuscript_hands","hand_id","bigint"
"manuscript_hands","manuscript_id","bigint"
"manuscript_hands","script_name_id","bigint"
"manuscript_hands","hand_name_in_ms","varchar"
"watermarks","id","bigint"
"watermarks","name","varchar"
"watermarks","external_id","int"
"watermarks","watermark_img","varchar"
"watermarks","comment","longtext"
"watermarks","entry_date","datetime"
"watermarks","data_contributor_id","bigint"
"bindings","id","bigint"
"bindings","max_height","decimal"
"bindings","max_width","decimal"
"bindings","block_max","decimal"
"bindings","decoration_comment","longtext"
"bindings","general_comments","longtext"
"bindings","entry_date","datetime"
"bindings","data_contributor_id","bigint"
"bindings","date_id","bigint",foreign key to time_reference table
"bindings","manuscript_id","bigint"
"bindings","place_of_origin_id","bigint"
"bindings","style_of_binding_id","bigint"
"bindings","type_of_binding_id","bigint"
"bindings","category","varchar", can be: "original", ("early" meaning "early modern"),("historical" meaning "Historical rebinding"),("conservation" meaning "Conservation binding"),("restored" meaning "Restored binding")
"manuscript_watermarks","id","bigint"
"manuscript_watermarks","where_in_manuscript","varchar"
"manuscript_watermarks","manuscript_id","bigint"
"manuscript_watermarks","watermark_id","bigint"
"music_notation_names","id","bigint"
"music_notation_names","name","varchar"
"content","id","bigint"
"content","formula_text","longtext"
"content","original_or_added","varchar"
"content","biblical_reference","varchar"
"content","reference_to_other_items","varchar"
"content","similarity_by_user","varchar", can be "0" meaning "the formula not in the editions"),("0.5" meaning "paraphrase"),("1" meaning "exact match"
"content","entry_date","datetime"
"content","sequence_in_ms","int"
"content","edition_index_id","bigint"
"content","comments","longtext"
"content","data_contributor_id","bigint"
"content","formula_id","bigint",foreign id for the formulas table
"content","function_id","bigint"
"content","liturgical_genre_id","bigint"
"content","music_notation_id","bigint"
"content","quire_id","bigint"
"content","rite_id","bigint"
"content","section_id","bigint"
"content","subfunction_id","bigint"
"content","subsection_id","bigint"
"content","where_in_ms_from","decimal"
"content","where_in_ms_to","decimal"
"content","manuscript_id","bigint"
"content","rite_name_from_ms","varchar"
"content","rite_sequence","int"
"content","proper_texts","tinyint"
"content","similarity_levenshtein","double"
"content","similarity_levenshtein_percent","double"
"content","edition_subindex","varchar"
"content","subrite_name_from_ms","longtext"
"places","id","bigint"
"places","longitude","double"
"places","latitude","double"
"places","country_today_eng","varchar",use this if not told otherwise
"places","region_today_eng","varchar",use this if not told otherwise
"places","city_today_eng","varchar",use this if not told otherwise
"places","repository_today_eng","varchar",use this if not told otherwise
"places","place_type","varchar", can be "library", "center", "scriptory" or "multiple"
"quires","id","bigint"
"quires","sequence_of_the_quire","int"
"quires","type_of_the_quire","varchar", can be "bifolium","binion","ternion","quaternion","quinternion","seksternion","septernion","okternion"
"quires","where_in_ms_from","decimal"
"quires","where_in_ms_to","decimal"
"quires","graph_img","varchar"
"quires","comment","longtext"
"quires","entry_date","datetime"
"quires","data_contributor_id","bigint"
"quires","manuscript_id","bigint"
"quires","material","varchar", can be "parchment", "paper"
"names","id","bigint"
"names","name","varchar"
"calendar_authors","id","bigint"
"calendar_authors","calendar_id","bigint"
"calendar_authors","contributors_id","bigint"
"rite_names","id","bigint"
"rite_names","name","varchar"
"rite_names","english_translation","varchar"
"rite_names","votive","tinyint"
"rite_names","section_id","bigint"
"indexerapp_clla","id","bigint"
"indexerapp_clla","clla_no","varchar"
"indexerapp_clla","liturgical_genre","varchar"
"indexerapp_clla","dating_comment","longtext"
"indexerapp_clla","provenance_comment","longtext"
"indexerapp_clla","comment","longtext"
"indexerapp_clla","dating_id","bigint"
"indexerapp_clla","manuscript_id","bigint"
"indexerapp_clla","provenance","varchar"
"sections","id","bigint"
"sections","name","varchar"
"sections","parent_section_id","bigint"
"subjects","id","bigint"
"subjects","name","varchar"
"time_reference","id","bigint"
"time_reference","time_description","varchar"
"time_reference","century_from","int"
"time_reference","century_to","int"
"time_reference","year_from","int"
"time_reference","year_to","int"
"origins","id","bigint"
"origins","origins_comment","longtext"
"origins","provenance_comments","longtext"
"origins","entry_date","datetime"
"origins","data_contributor_id","bigint"
"origins","manuscript_id","bigint"
"origins","origins_date_id","bigint", foreign key to time_reference table
"origins","origins_place_id","bigint"
"layouts_authors","id","bigint"
"layouts_authors","layouts_id","bigint"
"layouts_authors","contributors_id","bigint"
"manuscript_music_notations_authors","id","bigint"
"manuscript_music_notations_authors","manuscriptmusicnotations_id","bigint"
"manuscript_music_notations_authors","contributors_id","bigint"
"manuscripts_authors","id","bigint"
"manuscripts_authors","manuscripts_id","bigint"
"manuscripts_authors","contributors_id","bigint"
"origins_authors","id","bigint"
"origins_authors","origins_id","bigint"
"origins_authors","contributors_id","bigint"
"provenance_authors","id","bigint"
"provenance_authors","provenance_id","bigint"
"provenance_authors","contributors_id","bigint"
"quires_authors","id","bigint"
"quires_authors","quires_id","bigint"
"quires_authors","contributors_id","bigint"
"bindings_authors","id","bigint"
"bindings_authors","binding_id","bigint"
"bindings_authors","contributors_id","bigint"
"manuscript_hands_authors","id","bigint"
"manuscript_hands_authors","manuscripthands_id","bigint"
"manuscript_hands_authors","contributors_id","bigint"
"manuscripts","id","bigint"
"manuscripts","name","varchar"
"manuscripts","rism_id","varchar"
"manuscripts","foreign_id","varchar"
"manuscripts","shelf_mark","varchar"
"manuscripts","liturgical_genre_comment","longtext"
"manuscripts","common_name","varchar"
"manuscripts","dating_comment","longtext"
"manuscripts","place_of_origin_comment","longtext"
"manuscripts","how_many_columns_mostly","int"
"manuscripts","lines_per_page_usually","int"
"manuscripts","how_many_quires","int"
"manuscripts","quires_comment","longtext"
"manuscripts","foliation_or_pagination","varchar", can be "FOLIATION" or "PAGINATION"
"manuscripts","decorated","tinyint"
"manuscripts","decoration_comments","longtext"
"manuscripts","music_notation","tinyint"
"manuscripts","music_notation_comments","longtext"
"manuscripts","links","varchar"
"manuscripts","iiif_manifest_url","varchar"
"manuscripts","entry_date","datetime"
"manuscripts","binding_date_id","bigint", foreign key to time_reference table
"manuscripts","binding_place_id","bigint"
"manuscripts","contemporary_repository_place_id","bigint"
"manuscripts","data_contributor_id","bigint"
"manuscripts","dating_id","bigint"
"manuscripts","main_script_id","bigint"
"manuscripts","place_of_origin_id","bigint"
"manuscripts","image","varchar"
"manuscripts","general_comment","longtext"
"manuscripts","additional_url","varchar"
"manuscripts","display_as_main","tinyint"
"manuscripts","connected_ms","longtext"
"manuscripts","form_of_an_item","varchar", can be ("C" for "CODEX"),("F" for "FRAGMENT"),("P" for "PALIMPSEST"),("L" for "LOST")
"manuscripts","where_in_connected_ms","longtext"
"codicology_authors","id","bigint"
"codicology_authors","codicology_id","bigint"
"codicology_authors","contributors_id","bigint"
"indexerapp_editioncontent","id","bigint"
"indexerapp_editioncontent","feast_rite_sequence","decimal"
"indexerapp_editioncontent","subsequence","int"
"indexerapp_editioncontent","page","int"
"indexerapp_editioncontent","entry_date","datetime"
"indexerapp_editioncontent","bibliography_id","bigint"
"indexerapp_editioncontent","data_contributor_id","bigint"
"indexerapp_editioncontent","formula_id","bigint"
"indexerapp_editioncontent","function_id","bigint"
"indexerapp_editioncontent","rite_name_standarized_id","bigint"
"indexerapp_editioncontent","subfunction_id","bigint"
"condition_authors","id","bigint"
"condition_authors","condition_id","bigint"
"condition_authors","contributors_id","bigint"
"content_authors","id","bigint"
"content_authors","content_id","bigint"
"content_authors","contributors_id","bigint"
"indexerapp_msprojects","id","bigint"
"indexerapp_msprojects","manuscript_id","bigint"
"indexerapp_msprojects","project_id","bigint"
"decoration_authors","id","bigint"
"decoration_authors","decoration_id","bigint"
"decoration_authors","contributors_id","bigint"
"manuscript_music_notations","id","bigint"
"manuscript_music_notations","sequence_in_ms","int"
"manuscript_music_notations","where_in_ms_from","decimal"
"manuscript_music_notations","where_in_ms_to","decimal"
"manuscript_music_notations","original","tinyint"
"manuscript_music_notations","on_lines","tinyint"
"manuscript_music_notations","music_custos","tinyint"
"manuscript_music_notations","number_of_lines","int"
"manuscript_music_notations","comment","longtext"
"manuscript_music_notations","entry_date","datetime"
"manuscript_music_notations","data_contributor_id","bigint"
"manuscript_music_notations","dating_id","bigint"
"manuscript_music_notations","manuscript_id","bigint"
"manuscript_music_notations","music_notation_name_id","bigint"
"indexerapp_editioncontent_authors","id","bigint"
"indexerapp_editioncontent_authors","editioncontent_id","bigint"
"indexerapp_editioncontent_authors","contributors_id","bigint"
"watermarks_authors","id","bigint"
"watermarks_authors","watermarks_id","bigint"
"watermarks_authors","contributors_id","bigint"

If user asks about some table - sql should output all columns from that table.
If user asks about some place reffered by current, modern name, look in the columns with suffix _today_eng.
century_from is ALWAYS less than century_to - this represents range between century_from and century_to
year_from is ALWAYS less than year_to - this represents range between year_from and year_to
For example proper way for asking about century between 5 and 15 is:
`century_from` >= 5 AND `time_reference`.`century_to` <= 15

Do not use any column that was not mentioned above!
Date of the manuscript is the date for all its content.

When you are asked about formula text - it can be saved as formula_text or as formula_id reference to formulas table, which have "text" column. Always look in both places. 
e.g. If you use:
``` WHERE (`content`.`formula_text` LIKE '%some_text%' ```
Always od this OR statement too:
```
WHERE (`content`.`formula_text` LIKE '%some_text%' 
   OR `content`.`formula_id` IN (
    SELECT `formulas`.`id` FROM `formulas` WHERE `formulas`.`text` LIKE '%some_text%'
))
```

scribes, scribblers are in the Hands table. Scribes is another name of Hands.

User can reffer to the following manuscripts by name rism or foreign id. If so, then filter the query with the proper ids:

Dont use comments columns. Always try to find the best table match for task.
If you dont know, or not sure about what table to use or what columnt to use - ask user in the sql comment!

"""+get_all_manuscript_names(projectId),
            tools=[{"type": "code_interpreter"}],
            model="gpt-4o",
        )
        # Cache the assistant instance with a timeout (e.g., 24*1 hour)
        cache.set(f'assistant_{user_api_key}', assistant, timeout=24*3600)
    return assistant

def gpt_generate_sql(request, question,projectId):
    response = {
        'text': "",
        'sql': ""
    }

    # Get the current user
    current_user = request.user

    # Retrieve the API key from the database
    try:
        user_api_key = UserOpenAIAPIKey.objects.get(user=current_user).api_key
    except UserOpenAIAPIKey.DoesNotExist:
        response['text']='API key not found for user'
        return response

    # Get or create the assistant for the user
    assistant = get_or_create_assistant(user_api_key,projectId)

    # Create a new thread for the user
    client = OpenAI(api_key=user_api_key)
    thread = client.beta.threads.create()

    message = client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=question
    )

    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread.id,
        assistant_id=assistant.id,
    )


    if run.status == 'completed': 

        messages = client.beta.threads.messages.list(
            thread_id=thread.id
        )
        #for msg in messages:
        #    for block in msg.content:
        #        print(block.text.value)

        #print("-------------RAW MSG------------")
        for msg in messages:
            #print(msg)
            #print('-----------')

            if msg.assistant_id and len(msg.assistant_id)>1:
                full_mess = msg.content[0].text.value

                #Extracting comments:
                lines = full_mess.split('\n')
                comments = [line for line in lines if line.startswith('--')]
                full_mess = '\n'.join([line for line in lines if not line.startswith('--')])

                #extracting sql:
                sql_match = re.search(r"```([\w\W]*?)```", full_mess, re.DOTALL)

                #matches = [m.group(1) for m in re.finditer("```([\w\W]*?)```", s)]
                if sql_match:
                    sql_code = sql_match.group(1).strip()
                else:
                    sql_code = full_mess.strip()


                sql_code = sql_code.replace("sql\n","")
                comments = '<br />'.join(comments).replace("--","").replace("\n","<br />")


                response['sql'] = sql_code
                response['text'] = comments

                #print("-------------SQL------------")
                #print(sql_code)

                #print("-------------TEXT------------")
                #print(comments)

                break


    else:
        response['text'] = str(run.status)
        #print(run.status)

    
    #response['sql'] = "SELECT * from manuscripts;"

    return response;
    