from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsProcessingParameterString,
    QgsProcessingException,
    QgsRasterLayer,
    QgsProject,
    QgsCoordinateTransform,
    QgsCoordinateReferenceSystem
)

import ee
import json

from datetime import datetime


class SerieTemporalDesmatamento(QgsProcessingAlgorithm):

    INPUT_AOI = 'INPUT_AOI'
    SATELITE = 'SATELITE'
    DATA_INI = 'DATA_INI'
    DATA_FIM = 'DATA_FIM'
    NUVEM = 'NUVEM'
    MAX_IMAGENS = 'MAX_IMAGENS'
    EE_PROJECT = 'EE_PROJECT'

    # =========================================================

    def initAlgorithm(self, config=None):

        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_AOI,
                'Área de interesse',
                [QgsProcessing.TypeVectorPolygon]
            )
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.SATELITE,
                'Satélite',
                options=[
                    'Landsat (05 08 09)',
                    'Sentinel-2'
                ],
                defaultValue=0
            )
        )

        self.addParameter(
            QgsProcessingParameterString(
                self.DATA_INI,
                'Data inicial (DD/MM/AAAA)',
                defaultValue='01/01/2020'
            )
        )

        self.addParameter(
            QgsProcessingParameterString(
                self.DATA_FIM,
                'Data final (DD/MM/AAAA)',
                defaultValue='31/12/2024'
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.NUVEM,
                'Cobertura máxima de nuvens (%)',
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=20,
                minValue=0,
                maxValue=100
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.MAX_IMAGENS,
                'Máximo de imagens',
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=20,
                minValue=1,
                maxValue=500
            )
        )

        self.addParameter(
            QgsProcessingParameterString(
                self.EE_PROJECT,
                'Projeto Google Earth Engine',
                defaultValue='geonat-495314'
            )
        )

    # =========================================================

    def processAlgorithm(self, parameters, context, feedback):

        layer = self.parameterAsVectorLayer(
            parameters,
            self.INPUT_AOI,
            context
        )

        sat = self.parameterAsEnum(
            parameters,
            self.SATELITE,
            context
        )

        data_ini_br = self.parameterAsString(
            parameters,
            self.DATA_INI,
            context
        )

        data_fim_br = self.parameterAsString(
            parameters,
            self.DATA_FIM,
            context
        )

        nuvem = self.parameterAsInt(
            parameters,
            self.NUVEM,
            context
        )

        max_imgs = self.parameterAsInt(
            parameters,
            self.MAX_IMAGENS,
            context
        )

        projeto = self.parameterAsString(
            parameters,
            self.EE_PROJECT,
            context
        )

        # =====================================================
        # DATAS
        # =====================================================

        data_ini_obj = datetime.strptime(
            data_ini_br,
            '%d/%m/%Y'
        )

        data_fim_obj = datetime.strptime(
            data_fim_br,
            '%d/%m/%Y'
        )

        start = data_ini_obj.strftime('%Y-%m-%d')
        end = data_fim_obj.strftime('%Y-%m-%d')

        # =====================================================
        # EARTH ENGINE
        # =====================================================

        try:

            ee.Initialize(project=projeto)

        except:

            ee.Authenticate(force=True)

            ee.Initialize(project=projeto)

        # =====================================================
        # AOI
        # =====================================================

        geom_total = None

        for f in layer.getFeatures():

            if geom_total is None:

                geom_total = f.geometry()

            else:

                geom_total = geom_total.combine(
                    f.geometry()
                )

        crs_src = layer.crs()

        crs_dest = QgsCoordinateReferenceSystem(
            'EPSG:4326'
        )

        if crs_src != crs_dest:

            transform = QgsCoordinateTransform(
                crs_src,
                crs_dest,
                QgsProject.instance()
            )

            geom_total.transform(transform)

        aoi = ee.Geometry(
            json.loads(
                geom_total.asJson()
            )
        )

        # =====================================================
        # PREVIEW LANDSAT 5
        # =====================================================

        def preview_l57(img):

            qa = img.select('QA_PIXEL')

            mask = (
                qa.bitwiseAnd(1 << 1).eq(0)
                .And(qa.bitwiseAnd(1 << 2).eq(0))
                .And(qa.bitwiseAnd(1 << 3).eq(0))
                .And(qa.bitwiseAnd(1 << 4).eq(0))
            )

            return (
                img.updateMask(mask)
                .select(
                    ['SR_B3', 'SR_B2', 'SR_B1'],
                    ['R', 'G', 'B']
                )
                .multiply(0.0000275)
                .add(-0.2)
                .clamp(0, 0.3)
                .unitScale(0, 0.3)
            )

        # =====================================================
        # PREVIEW LANDSAT 8/9
        # =====================================================

        def preview_l89(img):

            qa = img.select('QA_PIXEL')

            mask = (
                qa.bitwiseAnd(1 << 1).eq(0)
                .And(qa.bitwiseAnd(1 << 2).eq(0))
                .And(qa.bitwiseAnd(1 << 3).eq(0))
                .And(qa.bitwiseAnd(1 << 4).eq(0))
            )

            return (
                img.updateMask(mask)
                .select(
                    ['SR_B4', 'SR_B3', 'SR_B2'],
                    ['R', 'G', 'B']
                )
                .multiply(0.0000275)
                .add(-0.2)
                .clamp(0, 0.3)
                .unitScale(0, 0.3)
            )

        # =====================================================
        # PREVIEW SENTINEL
        # =====================================================

        def preview_sentinel(img):

            qa = img.select('QA60')

            cloud = qa.bitwiseAnd(1 << 10).eq(0)

            cirrus = qa.bitwiseAnd(1 << 11).eq(0)

            mask = cloud.And(cirrus)

            return (
                img.updateMask(mask)
                .select(
                    ['B4', 'B3', 'B2'],
                    ['R', 'G', 'B']
                )
                .divide(10000)
                .clamp(0, 0.3)
                .unitScale(0, 0.3)
            )

        # =====================================================
        # LANDSAT
        # =====================================================

        if sat == 0:

            col5 = (
                ee.ImageCollection(
                    'LANDSAT/LT05/C02/T1_L2'
                )
                .filterBounds(aoi)
                .filterDate(start, end)
                .filter(
                    ee.Filter.lt(
                        'CLOUD_COVER',
                        nuvem
                    )
                )
            )

            col8 = (
                ee.ImageCollection(
                    'LANDSAT/LC08/C02/T1_L2'
                )
                .filterBounds(aoi)
                .filterDate(start, end)
                .filter(
                    ee.Filter.lt(
                        'CLOUD_COVER',
                        nuvem
                    )
                )
            )

            col9 = (
                ee.ImageCollection(
                    'LANDSAT/LC09/C02/T1_L2'
                )
                .filterBounds(aoi)
                .filterDate(start, end)
                .filter(
                    ee.Filter.lt(
                        'CLOUD_COVER',
                        nuvem
                    )
                )
            )

            col = (
                col5
                .merge(col8)
                .merge(col9)
                .sort('system:time_start')
                .limit(max_imgs)
            )

        # =====================================================
        # SENTINEL
        # =====================================================

        else:

            col = (
                ee.ImageCollection(
                    'COPERNICUS/S2_SR_HARMONIZED'
                )
                .filterBounds(aoi)
                .filterDate(start, end)
                .filter(
                    ee.Filter.lt(
                        'CLOUDY_PIXEL_PERCENTAGE',
                        nuvem
                    )
                )
                .sort('system:time_start')
                .limit(max_imgs)
            )

        # =====================================================
        # LOOP
        # =====================================================

        quantidade = col.size().getInfo()

        lista = col.toList(quantidade)

        for i in range(quantidade):

            img_original = ee.Image(
                lista.get(i)
            )

            data = (
                ee.Date(
                    img_original.get(
                        'system:time_start'
                    )
                )
                .format('YYYY-MM-dd')
                .getInfo()
            )

            # =================================================
            # LANDSAT
            # =================================================

            if sat == 0:

                sat_id = img_original.get(
                    'SPACECRAFT_ID'
                ).getInfo()

                if 'LANDSAT_5' in sat_id:

                    sat_nome = 'Landsat_4-5'

                    img_preview = preview_l57(
                        img_original
                    )

                else:

                    sat_nome = 'Landsat_8-9'

                    img_preview = preview_l89(
                        img_original
                    )

            # =================================================
            # SENTINEL
            # =================================================

            else:

                sat_nome = 'Sentinel-2'

                img_preview = preview_sentinel(
                    img_original
                )

            # =================================================
            # NOME LAYER
            # =================================================

            nome_layer = (
                f'{data}_{sat_nome}'
            )

            # =================================================
            # MAP ID
            # =================================================

            map_id = img_preview.getMapId()

            url = (
                map_id['tile_fetcher']
                .url_format
            )

            # =================================================
            # CAMADA XYZ
            # =================================================

            rlayer = QgsRasterLayer(
                f'type=xyz&url={url}',
                nome_layer,
                'wms'
            )

            # =================================================
            # ADICIONAR AO FINAL
            # =================================================

            if rlayer.isValid():

                # =============================================
                # NÃO inserir automaticamente
                # =============================================

                QgsProject.instance().addMapLayer(
                    rlayer,
                    False
                )

                # =============================================
                # ROOT
                # =============================================

                root = QgsProject.instance().layerTreeRoot()

                # =============================================
                # INSERIR NO FINAL
                # =============================================

                root.addLayer(
                    rlayer
                )

                feedback.pushInfo(
                    nome_layer
                )

        return {}

    # =========================================================

    def name(self):
        return 'catalogo_temporal'

    def displayName(self):
        return 'Carregar imagens Google Engine'

    def group(self):
        return 'GeoNat'

    def groupId(self):
        return 'geonat'

    def createInstance(self):
        return SerieTemporalDesmatamento()