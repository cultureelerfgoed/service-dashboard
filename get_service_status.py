import os
import json
from urllib.parse import urlsplit
from datetime import date, timedelta, datetime, timezone
import requests
from SPARQLWrapper import SPARQLWrapper, JSON

TOKEN = os.getenv('POOLPARTY_TOKEN')
STATES = {
    'OK': '![#339900](https://placehold.co/5x5/339900/339900.png)',
    'WARNING': '![#ec942c](https://placehold.co/5x5/ec942c/ec942c.png)',
    'FAIL': '![#f03c15](https://placehold.co/5x5/f03c15/f03c15.png)',
}

def poolparty_test(url: str, description: str, token: str) -> str:
    try:
        if token:
            response = requests.get(url, allow_redirects=True, headers={'Authorization': f'{token}'}, timeout=120)
            if response.status_code == 200 and 'uri' in str(response.content):
                status = STATES['OK']
            else:
                status = STATES['FAIL']
            millis = response.elapsed / timedelta(milliseconds=1)
    
            return format_status(status, f'[{urlsplit(url).netloc}]({url}) : <b>{description}</b> : <b>{response.status_code}</b> in {millis}ms.')
        else:
            return format_status(STATES['WARN'], 'Unable to authenticate.')
    except Exception as e:
            print(e)
            return format_status(STATES['FAIL'], f'fout bij ophalen status code van: {url}')
    
def check_status_code(url: str) -> str:
    try:
        response = requests.get(url, allow_redirects=True)
        
        if response.status_code == 200:
            status = STATES['OK']
        else:
            status = STATES['FAIL']
        millis = response.elapsed / timedelta(milliseconds=1)

        return format_status(status, f'[{urlsplit(url).netloc}]({url}) : <b>{response.status_code}</b> in {millis}ms.')

    except Exception as e:
        print(e)
        return format_status(STATES['FAIL'], f'fout bij ophalen status code van: {url}')


def check_ldv_service_status(service_uri: str) -> str:
    """ Validate against endpoint """
    headers = {'accept': 'text/plain'}
    timeformat_src = '%Y-%m-%dT%H:%M:%S.%fZ'

    try:
        response = requests.get(service_uri, headers=headers, timeout=100)
        item_info = json.loads(response.content)
        nm = item_info.get('name')
        st = item_info.get('status')
        sy = item_info.get('outOfSync')
        ty = item_info.get('type')
        cr = datetime.strptime(item_info.get('createdAt'), timeformat_src)
        now_cet = (datetime.now(timezone.utc) + timedelta(hours=2)).replace(tzinfo=None)
        
        if st != 'running':
            status = STATES['FAIL']
        elif sy == 'true':
            status = STATES['WARNING']
        elif now_cet - cr <= timedelta(days=1):
             status = STATES['WARNING']
        else:
            status = STATES['OK']

        return format_status(status, f'[{nm}:{ty}]({service_uri}) <b>{st}</b> sinds {str(cr)[:-3]} sync nodig: <b>{sy}</b>.')
    except TimeoutError as te:
        print('Error getting endpoint description: %s', str(te))
        return format_status(STATES['FAIL'], f'fout bij ophalen status code: <b>{service_uri}</b>')


def check_datacatalog_on_dataregister() -> str:
    nde_sparql = SPARQLWrapper('https://datasetregister.netwerkdigitaalerfgoed.nl/sparql')
    nde_sparql.setReturnFormat(JSON)

    rce_sparql = SPARQLWrapper('https://api.linkeddata.cultureelerfgoed.nl/datasets/rce/datacatalog/services/datacatalog/sparql')
    rce_sparql.setReturnFormat(JSON)

    # query to count datasets on nde datasetregister published by rce and read recently
    nde_sparql.setQuery(
        'PREFIX dct: <http://purl.org/dc/terms/>' \
        'PREFIX schema: <https://schema.org/>' \
        'PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>' \
        'SELECT (count(distinct ?dataset) as ?count) WHERE {' \
        '?dataset dct:publisher <https://www.cultureelerfgoed.nl> .' \
        '?dataset schema:dateRead ?date .' \
        f'FILTER (?date > "{date.today() - timedelta(days=2)}T00:00:00+00:00"^^xsd:dateTime) .' \
        '} ' 
    )

    # query to count datasets in rce catalog
    rce_sparql.setQuery('''
        PREFIX schema: <https://schema.org/>
        SELECT (count(distinct ?dataset) as ?count) WHERE {
        ?dataset schema:publisher <https://www.cultureelerfgoed.nl> .
        } '''
    )

    try:
        nde_q = nde_sparql.queryAndConvert()
        set_count_nde = nde_q['results']['bindings'][0]['count']['value']
        rce_q = rce_sparql.queryAndConvert()
        set_count_rce = rce_q['results']['bindings'][0]['count']['value']

        if set_count_nde == set_count_rce:
            status = STATES['OK']
        else:
            status = STATES['FAIL']

        return format_status(status, f'<b>{set_count_nde}/{set_count_rce}</b> datasets uit de datacatalog van de RCE beschikbaar op het NDE Datasetregister. ')
    except Exception as e:
        print(e)
        return format_status(STATES['FAIL'], 'fout bij valideren datacatalogus op het datasetregister.')


def format_status(status: str, msg: str) -> str:
    now_cet = (datetime.now(timezone.utc) + timedelta(hours=2)).replace(tzinfo=None)
    return f'{status} [{now_cet:%Y-%m-%d %H:%M}] {msg} <br /> \n'

def main():
    test_list = [
        check_datacatalog_on_dataregister(),
        check_ldv_service_status('https://api.linkeddata.cultureelerfgoed.nl/datasets/rce/datacatalog/services/datacatalog'),
        check_ldv_service_status('https://api.linkeddata.cultureelerfgoed.nl/datasets/rce/cho/services/cho/'),
        check_ldv_service_status('https://api.linkeddata.cultureelerfgoed.nl/datasets/thesauri/cht/services/cht-jena/'),
        check_ldv_service_status('https://api.linkeddata.cultureelerfgoed.nl/datasets/thesauri/cht/services/cht-virtuoso/'),
        check_ldv_service_status('https://api.linkeddata.cultureelerfgoed.nl/datasets/thesauri/archeologischbasisregister/services/archeologischbasisregister-jena/'),
        poolparty_test('https://digitaalerfgoed-test.poolparty.biz/PoolParty/api/thesaurus/312d0e18-773b-45eb-95ff-51a94d760967/concept?concept=https://digitaalerfgoed-test.poolparty.biz/term/id/cht/9f841236-c0d0-4583-bfab-b2e8ddcf8fec&properties=all', 'Get concept status', TOKEN),
        poolparty_test('https://digitaalerfgoed-test.poolparty.biz/PoolParty/api/thesaurus/312d0e18-773b-45eb-95ff-51a94d760967/narrowers?concept=https://digitaalerfgoed-test.poolparty.biz/term/id/cht/04770e4f-1c11-40e7-a256-9de8c6d569c6&properties=all', 'Get narrowers', TOKEN),
        poolparty_test('https://digitaalerfgoed-test.poolparty.biz/PoolParty/api/thesaurus/312d0e18-773b-45eb-95ff-51a94d760967/broaders?concept=https://digitaalerfgoed-test.poolparty.biz/term/id/cht/9f841236-c0d0-4583-bfab-b2e8ddcf8fec&properties=all&properties=all', 'Get broaders', TOKEN),
        poolparty_test('https://data.cultureelerfgoed.nl/PoolParty/api/thesaurus/1DF17ED4-4A38-0001-C6FF-883013B04AD0/concept?concept=https://data.cultureelerfgoed.nl/term/id/cht/1b8bd4e8-d51c-4ae2-8c16-c56751e2c470&properties=all&language=de','Zoeken concept', TOKEN),
        poolparty_test('https://data.cultureelerfgoed.nl/PoolParty/api/thesaurus/1DF17ED4-4A38-0001-C6FF-883013B04AD0/concept?concept=https://data.cultureelerfgoed.nl/term/id/cht/1685e55b-68a3-421f-9bf8-a64b6ec269b7', 'Geef me de het prefLabel van een bepaalde term.', TOKEN),
        poolparty_test('https://data.cultureelerfgoed.nl/extractor/api/suggest?projectId=1DF17ED4-4A38-0001-C6FF-883013B04AD0&language=nl&searchString=gotiek', 'Staat een bepaalde term in de thesaurus?', TOKEN),
        check_status_code('https://kennis.cultureelerfgoed.nl/index.php/Datasets_van_de_RCE'),
        check_status_code('https://beeldbank.cultureelerfgoed.nl/'),
        check_status_code('https://www.cultureelerfgoed.nl/'),
        ]
    with open("README.md", "w") as f:
        f.write(f'# Services <br /> \n')
        for entry in test_list:
            f.write(entry)
    
if __name__ == "__main__":
    main()
