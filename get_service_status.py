import json
from urllib.parse import urlsplit
import requests
from SPARQLWrapper import SPARQLWrapper, JSON
from datetime import date, timedelta, datetime

STATES = {
    'OK': '![#339900](https://placehold.co/5x5/339900/339900.png)',
    'WARNING': '![#ec942c](https://placehold.co/5x5/ec942c/ec942c.png)',
    'FAIL': '![#f03c15](https://placehold.co/5x5/f03c15/f03c15.png)',
}
def check_status_code(url: str) -> str:
    try:
        response = requests.get(url, allow_redirects=True)
        
        if response.status_code == 200:
            status = STATES['OK']
        else:
            status = STATES['FAIL']
        millis = response.elapsed / timedelta(milliseconds=1)

        return format_status(status, f'[{urlsplit(url).netloc}]({url}) status code: <b>{response.status_code}</b> respons duurde {millis}ms. <br /> \n')

    except Exception as e:
        print(e)


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

        if st != 'running':
            status = STATES['FAIL']
        elif sy == 'true':
            status = STATES['WARNING']
        elif datetime.now() - cr <= timedelta(days=1):
             status = STATES['WARNING']
        else:
            status = STATES['OK']

        return format_status(status, f'service {nm}:{ty} <b>{st}</b> sinds {cr} synchronisatie nodig: <b>{sy}</b>.  <br /> \n')
    except TimeoutError as te:
        print('Error getting endpoint description: %s', str(te))

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

        return format_status(status, f'<b>{set_count_nde}/{set_count_rce}</b> datasets uit de datacatalog van de RCE beschikbaar op het NDE Datasetregister.  <br /> \n')
    except Exception as e:
        print(e)

def format_status(status: str, msg: str) -> str:
    return f'{status} [{datetime.now():%Y-%m-%d %H:%M.%S}] {msg}'

def main():
    test_list = [
        check_datacatalog_on_dataregister(),
        check_ldv_service_status('https://api.linkeddata.cultureelerfgoed.nl/datasets/rce/datacatalog/services/datacatalog'),
        check_ldv_service_status('https://api.linkeddata.cultureelerfgoed.nl/datasets/rce/cho/services/cho/'),
        check_ldv_service_status('https://api.linkeddata.cultureelerfgoed.nl/datasets/thesauri/cht/services/cht-jena/'),
        check_ldv_service_status('https://api.linkeddata.cultureelerfgoed.nl/datasets/thesauri/cht/services/cht-virtuoso/'),
        check_ldv_service_status('https://api.linkeddata.cultureelerfgoed.nl/datasets/thesauri/archeologischbasisregister/services/archeologischbasisregister-jena/'),
        check_status_code('https://data.cultureelerfgoed.nl/term/id/abr/b402446a-0a00-4fee-a9cd-1a7f307d651e.html')
        ]
    with open("README.md", "w") as f:
        f.write(f'# Services <br /> \n')
        for entry in test_list:
            f.write(entry)
    
if __name__ == "__main__":
    main()