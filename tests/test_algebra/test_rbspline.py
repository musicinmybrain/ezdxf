# Created: 06.01.2012
# Copyright (c) 2012 Manfred Moitzi
# License: MIT License
from ezdxf.algebra.bspline import BSpline, BSplineU
from ezdxf.algebra.base import equals_almost

DEFPOINTS = [(0.0, 0.0, 0.0), (10., 20., 20.), (30., 10., 25.), (40., 10., 25.), (50., 0., 30.)]
DEFWEIGHTS = [1, 10, 10, 10, 1]


def test_rbspline():
    curve = BSpline(DEFPOINTS, order=3, weights=DEFWEIGHTS)
    expected = RBSPLINE
    points = list(curve.approximate(40))

    for rpoint, epoint in zip(points, expected):
        epx, epy, epz = epoint
        rpx, rpy, rpz = rpoint
        assert equals_almost(epx, rpx)
        assert equals_almost(epy, rpy)
        assert equals_almost(epz, rpz)


def test_rbsplineu():
    curve = BSplineU(DEFPOINTS, order=3, weights=DEFWEIGHTS)
    expected = RBSPLINEU
    points = list(curve.approximate(40))

    for rpoint, epoint in zip(points, expected):
        epx, epy, epz = epoint
        rpx, rpy, rpz = rpoint
        assert equals_almost(epx, rpx)
        assert equals_almost(epy, rpy)
        assert equals_almost(epz, rpz)


RBSPLINE = [
    [0.0, 0.0, 0.0],
    [6.523511823865181, 12.435444414243, 12.618918184289209],
    [8.577555396711936, 15.546819156540385, 16.02930664760543],
    [9.79458577064345, 16.834444293293426, 17.66086246769147],
    [10.73345259391771, 17.441860465116278, 18.64937388193202],
    [11.566265060240964, 17.710843373493976, 19.337349397590362],
    [12.366884232222603, 17.777396083819994, 19.864307798007555],
    [13.17543722061015, 17.70449376519489, 20.29840796800251],
    [14.018691588785048, 17.52336448598131, 20.677570093457945],
    [14.918157331307409, 17.249119414324195, 21.025277988811382],
    [15.894039735099337, 16.887417218543046, 21.357615894039736],
    [16.967671444180215, 16.437431711549586, 21.68680506459284],
    [18.163471241170534, 15.893037336024218, 22.023208879919274],
    [19.510974923394407, 15.242949158901883, 22.376649365267962],
    [20.9875, 14.5125, 22.74375],
    [22.421875, 13.828125, 23.0859375],
    [23.799999999999997, 13.2, 23.4],
    [25.121875000000003, 12.628125000000004, 23.685937500000005],
    [26.387500000000003, 12.112500000000002, 23.94375],
    [27.596875, 11.653125, 24.1734375],
    [28.75, 11.25, 24.375],
    [29.846874999999997, 10.903125, 24.5484375],
    [30.887500000000003, 10.6125, 24.69375],
    [31.871875, 10.378125, 24.8109375],
    [32.8, 10.2, 24.900000000000002],
    [33.671875, 10.078125, 24.9609375],
    [34.4875, 10.0125, 24.993750000000002],
    [35.24482521418298, 9.999374648239638, 25.00031267588019],
    [35.923309788092844, 9.989909182643796, 25.00504540867811],
    [36.53191079118195, 9.968506973455877, 25.01574651327206],
    [37.086092715231786, 9.933774834437086, 25.03311258278146],
    [37.59928171835071, 9.88327923199116, 25.05836038400442],
    [38.084112149532714, 9.813084112149534, 25.093457943925237],
    [38.553838914594934, 9.716884950199985, 25.14155752490001],
    [39.02439024390243, 9.584335279972517, 25.20783236001374],
    [39.51807228915663, 9.397590361445783, 25.30120481927711],
    [40.07155635062611, 9.123434704830053, 25.438282647584973],
    [40.75635967895525, 8.692694871446063, 25.653652564276967],
    [41.74410293066476, 7.9342387419585405, 26.03288062902073],
    [43.59880402283228, 6.278880130470243, 26.860559934764876],
    [50.0, 0.0, 30.0]
]

RBSPLINEU = [
    [9.09090909090909, 18.18181818181818, 18.18181818181818],
    [9.395802632247573, 18.562935108491285, 18.631536155292444],
    [9.798110761252083, 18.762733839599925, 19.012780144471197],
    [10.282214894437072, 18.83002869256135, 19.350349021455187],
    [10.840282232200128, 18.794098781270048, 19.66003848620911],
    [11.469194312796208, 18.672985781990523, 19.952606635071092],
    [12.169005932571265, 18.477789031978006, 20.23585588192736],
    [12.94215853361622, 18.215018608048418, 20.515808145803625],
    [13.793103448275861, 17.887931034482758, 20.79741379310345],
    [14.728173496505788, 17.497293218281442, 21.08500935070048],
    [15.755627009646302, 17.041800643086816, 21.382636655948552],
    [16.88583288443867, 16.518267372223452, 21.69428689121962],
    [18.131592164741335, 15.921647413360123, 22.024108488196887],
    [19.50861179706793, 15.24491263167766, 22.37660592041512],
    [20.9875, 14.5125, 22.74375],
    [22.421875, 13.828125, 23.0859375],
    [23.8, 13.199999999999998, 23.399999999999995],
    [25.121875000000003, 12.628125000000004, 23.685937500000005],
    [26.387499999999992, 12.112500000000002, 23.943749999999998],
    [27.596874999999997, 11.653125000000001, 24.1734375],
    [28.75, 11.25, 24.375],
    [29.846875000000004, 10.903125, 24.548437500000002],
    [30.887500000000003, 10.6125, 24.69375],
    [31.871874999999996, 10.378125, 24.810937499999998],
    [32.8, 10.2, 24.900000000000002],
    [33.671875, 10.078125, 24.9609375],
    [34.4875, 10.0125, 24.99375],
    [35.24585039542372, 9.99968741208465, 25.000156293957684],
    [35.93671521848317, 9.994977398292315, 25.00251130085384],
    [36.564846794892105, 9.984473525777116, 25.007763237111444],
    [37.138263665594856, 9.967845659163988, 25.016077170418008],
    [37.66363725844023, 9.944551986613734, 25.027724006693134],
    [38.146551724137936, 9.913793103448276, 25.043103448275865],
    [38.59170115822057, 9.87443914994261, 25.062780425028688],
    [39.003038634061646, 9.824916799305457, 25.087541600347276],
    [39.383886255924175, 9.763033175355451, 25.118483412322274],
    [39.737010904425915, 9.685695958948045, 25.15715202052598],
    [40.06466532482549, 9.588454455911952, 25.205772772044025],
    [40.36858677532876, 9.464715688090386, 25.267642155954803],
    [40.6499313989532, 9.304334569846029, 25.347832715076986],
    [40.90909090909091, 9.09090909090909, 25.454545454545453]
]

if __name__ == "__main__":
    unittest.main()
