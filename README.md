# ckanext-dge-harvest

`ckanext-dge-harvest` es una extensión para CKAN utilizada en la plataforma [datos.gob.es](https://datos.gob.es/) para procesos de federación/cosechado (*harvesting*) y perfiles RDF asociados.

> [!TIP]
> Guía base y contexto del proyecto: https://github.com/datosgobes/datos.gob.es

## Descripción general

- Proporciona plugins CKAN para cosechado (*harvest*) y *harvesters* RDF.
- Registra perfiles RDF adicionales.
- Incluye un comando `ckan` de administración.

## Requisitos

- Una instancia de CKAN.
- Una instancia de [Virtuoso](https://github.com/openlink/virtuoso-opensource) como almacén de tripletas RDF; carga el grafo completo del catálogo de datos y provee de un punto de consulta SPARQL sobre el mismo.
- Librerías Python adicionales ([`requirements`](requirements.txt))/[`setup.py.install_requires`](setup.py)
- Requiere [`ckanext-dge-scheming`](https://github.com/datosgobes/ckanext-dge-scheming)

### Compatibilidad

Compatibilidad con versiones de CKAN:

| Versión de CKAN | ¿Compatible?                                                              |
|--------------|-----------------------------------------------------------------------------|
| 2.8          | ❌ No (requiere Python 3+)                                                   |
| 2.9          | ✅ Sí                                                                        |
| 2.10         | ❓ Desconocido                                                               |
| 2.11         | ❓ Desconocido                                                               |

## Instalación

```sh
pip install -r requirements.txt
pip install -e .
```

## Configuración

### Plugins

Activa los plugins en tu configuración de CKAN:

```ini
ckan.plugins = … dge_harvest dge_nti_rdf_harvester dge_dcat_ap_es_rdf_harvester
```

Los plugins disponibles son:

- `dge_harvest`: Plugin principal de cosechado (*harvest*).
- `dge_nti_rdf_harvester`: *Harvester* RDF para el perfil [NTI-RISP (2013)](https://datosgobes.github.io/NTI-RISP/).
- `dge_dcat_ap_es_rdf_harvester`: *Harvester* RDF para el perfil [DCAT-AP-ES](https://datosgobes.github.io/DCAT-AP-ES/).

**Perfiles RDF**:
- `dge_nti_profile`: Perfil para la serializaciñon en RDF conforme a [NTI-RISP (2013)](https://datosgobes.github.io/NTI-RISP/).
- `dge_dcat_ap_es_profile`: Perfil para la serialización en RDF conforme a [DCAT-AP-ES](https://datosgobes.github.io/DCAT-AP-ES/).

### Configuración en `ckan.ini`

> [!NOTE]
> La configuración específica de [datos.gob.es](https://datos.gob.es/) está documentada en:
> https://github.com/datosgobes/datos.gob.es/blob/master/docs/202512_datosgobes-ckan-doc_es.pdf (sección 3.11).

La documentación operativa de la plataforma muestra una activación conjunta típica de extensiones:

```ini
ckan.plugins = dge_brokenlinks dge dge_dashboard dge_ga_report dge_ga dcat
dge_harvest dge_nti_rdf_harvester dge_dcat_ap_es_rdf_harvester harvest fluent
scheming_datasets dge_dataservice dge_scheming stats report comments
dge_drupal_users
```

Ejemplo de parámetros específicos:

```ini
ckan.harvest.log_level = info

ckanext.dge_harvest.clear_jobs.interval = 1 month

ckanext.dge_harvest.dge_dcat_ap_es.url = https://datosgobes.github.io/DCAT-AP-ES
ckanext.dge_harvest.dge_dcat_ap_es.prefix = nota

ckanext.dge_harvest.virtuoso.sparql.endpoint = http://SPARQL_HOST:SPARQL_PORT/sparql
ckanext.dge_harvest.virtuoso.sparql.auth.endpoint = http://SPARQL_HOST:SPARQL_PORT/sparql-auth
ckanext.dge_harvest.virtuoso.username = SPARQL_USERNAME
ckanext.dge_harvest.virtuoso.password = SPARQL_PASSWORD
ckanext.dge_harvest.virtuoso.max_triples_per_query = 5000
ckanext.dge_harvest.virtuoso.batch_size.inserts = 1000
ckanext.dge_harvest.virtuoso.batch_size.inserts.min = 100
ckanext.dge_harvest.virtuoso.batch_size.updates = 1000
ckanext.dge_harvest.virtuoso.batch_size.updates.min = 100
ckanext.dge_harvest.virtuoso.batch_size.deletes = 50
ckanext.dge_harvest.virtuoso.batch_size.deletes.min = 10

ckanext.dge_harvest.max_attempts = 3

ckanext.dge_harvest.dcat_ap_es_1_0_0.config.filepath = ckan/ckanext-dge-harvest/ckanext/dge_harvest/config/dcat_ap_es_1_0_0_config.ini.template
ckanext.dge_harvest.template.path_emails = ruta al template de los email
ckanext.dge_harvest.language_report = es
ckanext.dge_harvest.shacl_report.use_preffix = true

# Parámetros de ckanext-harvest (cola/mensajería)
ckan.harvest.mq.type = redis
ckan.harvest.mq.hostname = REDIS_HOST
ckan.harvest.mq.port = REDIS_PORT
ckan.harvest.status_mail.errored = false
ckan.harvest.status_mail.all = false
```

### Migraciones de base de datos (harvest)

Para crear/actualizar el modelo de datos del federador (*harvest*):

```sh
ckan -c /etc/ckan/default/ckan.ini db upgrade -p harvest
```

### CLI (`ckan`)

> [!NOTE]
> A partir de CKAN 2.9, el comando `ckan` sustituye al histórico *paster* usado para tareas comunes de administración de CKAN.
> Consulta la [documentación de la CLI de CKAN](https://docs.ckan.org/en/2.9/maintaining/cli.html) para más detalles.

Este repositorio expone un comando:

- `dge_harvester`

Ejemplo de uso (ajusta el fichero `.ini` a tu entorno):

```sh
ckan -c /etc/ckan/default/ckan.ini dge_harvester
```

## Ejecución de tests

```sh
pytest --ckan-ini=test.ini ckanext/dge_harvest/tests
```

## Licencia

Este proyecto se distribuye bajo licencia **GNU Affero General Public License (AGPL) v3.0 o posterior**. Consulta el fichero [LICENSE](LICENSE).
