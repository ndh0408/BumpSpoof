"""
places.py — Vietnam preset destinations + OpenStreetMap (Nominatim) geocoding.

Presets let you jump straight to well-known spots; the search box resolves any
free-text query ("Chợ Bến Thành", "Cầu Vàng"...) to coordinates.
"""

from typing import Dict, List, Tuple

PlaceInfo = Tuple[float, float, str, str, str, str]

import requests

Coord = Tuple[float, float]

# Every entry carries its region and province so the UI can filter: a flat
# 271-item dropdown is unusable. The leading icon encodes the kind of stop.
# Mỗi điểm: (lat, lon, loại, tỉnh/thành, vùng, ghi chú)
VN_PLACE_INFO: Dict[str, PlaceInfo] = {
    # ── Nam (94 điểm) ──
    "💧 An Giang — Hồ Tà Pạ":
        (10.405, 104.995, "hồ", "An Giang", "Nam",
         "Hồ nước xanh trên núi Tà Pạ, Tri Tôn"),
    "🏞️ An Giang — Khu du lịch núi Sam":
        (10.67, 105.09, "danh thắng", "An Giang", "Nam",
         "Núi Sam linh thiêng, chùa cổ, lăng Thoại Ngọc Hầu"),
    "🏘️ An Giang — Làng Chăm Châu Giang":
        (10.7, 105.13, "làng bản dân tộc", "An Giang", "Nam",
         "Cộng đồng Chăm Islam, thánh đường, dệt thổ cẩm"),
    "🛕 An Giang — Miếu Bà Chúa Xứ Núi Sam":
        (10.682, 105.091, "chùa đền", "An Giang", "Nam",
         "Điểm hành hương lớn nhất miền Tây, Châu Đốc"),
    "⛰️ An Giang — Núi Cấm (Thiên Cấm Sơn)":
        (10.51, 105.0, "núi", "An Giang", "Nam",
         "Núi cao nhất miền Tây 705m, tượng Phật Di Lặc"),
    "🌿 An Giang — Rừng tràm Trà Sư":
        (10.585, 105.06, "thiên nhiên", "An Giang", "Nam",
         "Rừng tràm ngập nước từ 1983, cầu tre dài nhất VN (2020)"),
    "🏖️ Bà Rịa - Vũng Tàu — Bãi Sau Vũng Tàu":
        (10.34, 107.095, "biển", "Bà Rịa - Vũng Tàu", "Nam",
         "Bãi tắm chính, Thùy Vân"),
    "🏖️ Bà Rịa - Vũng Tàu — Côn Đảo - Bãi Đầm Trầu":
        (8.725, 106.605, "biển", "Bà Rịa - Vũng Tàu", "Nam",
         "Bãi biển đẹp nhất Côn Đảo gần sân bay"),
    "🏛️ Bà Rịa - Vũng Tàu — Côn Đảo - Nhà tù":
        (8.689, 106.608, "di tích", "Bà Rịa - Vũng Tàu", "Nam",
         "Di tích 'địa ngục trần gian', Chuồng Cọp"),
    "🏛️ Bà Rịa - Vũng Tàu — Côn Đảo - nghĩa trang Hàng Dương":
        (8.696, 106.61, "di tích", "Bà Rịa - Vũng Tàu", "Nam",
         "Nghĩa trang liệt sĩ, mộ Võ Thị Sáu"),
    "🏖️ Bà Rịa - Vũng Tàu — Hồ Cốc":
        (10.49, 107.33, "biển", "Bà Rịa - Vũng Tàu", "Nam",
         "Bãi biển hoang sơ Xuyên Mộc"),
    "🏞️ Bà Rịa - Vũng Tàu — Tượng Chúa Kitô Vua Vũng Tàu":
        (10.33, 107.087, "danh thắng", "Bà Rịa - Vũng Tàu", "Nam",
         "Tượng Chúa trên núi Nhỏ"),
    "🎡 Bình Dương — Khu du lịch Đại Nam":
        (10.935, 106.66, "vui chơi", "Bình Dương", "Nam",
         "Khu du lịch lớn: đền, vườn thú, biển nhân tạo"),
    "🧵 Bình Dương — Làng sơn mài Tương Bình Hiệp":
        (10.99, 106.645, "làng nghề", "Bình Dương", "Nam",
         "Làng nghề sơn mài truyền thống"),
    "🏛️ Bình Dương — Phố cổ Thủ Dầu Một":
        (10.976, 106.652, "di tích", "Bình Dương", "Nam",
         "Đường phố cổ kiến trúc Pháp, chùa cổ"),
    "⛰️ Bình Phước — Núi Bà Rá":
        (11.75, 106.98, "núi", "Bình Phước", "Nam",
         "Núi thiêng cao thứ 3 Nam Bộ, cáp treo"),
    "💧 Bình Phước — Thác Mơ Bình Phước":
        (11.83, 106.92, "hồ", "Bình Phước", "Nam",
         "Hồ thủy điện Thác Mơ, đảo trên hồ"),
    "🌿 Bình Phước — VQG Bù Gia Mập":
        (12.19, 107.2, "thiên nhiên", "Bình Phước", "Nam",
         "Rừng nguyên sinh biên giới Campuchia"),
    "🧵 Bạc Liêu — Cánh đồng muối Bạc Liêu":
        (9.18, 105.76, "làng nghề", "Bạc Liêu", "Nam",
         "Diêm dân làm muối truyền thống"),
    "🏞️ Bạc Liêu — Cánh đồng điện gió Bạc Liêu":
        (9.22, 105.77, "danh thắng", "Bạc Liêu", "Nam",
         "Turbine điện gió trên biển, điểm check-in"),
    "🏛️ Bạc Liêu — Khu lưu niệm Cao Văn Lầu":
        (9.285, 105.725, "di tích", "Bạc Liêu", "Nam",
         "Tưởng niệm tác giả Dạ cổ hoài lang"),
    "🏛️ Bạc Liêu — Nhà Công tử Bạc Liêu":
        (9.2857, 105.7244, "di tích", "Bạc Liêu", "Nam",
         "Dinh thự cổ của Trần Trinh Huy"),
    "🌿 Bạc Liêu — Vườn chim Bạc Liêu":
        (9.267, 105.742, "thiên nhiên", "Bạc Liêu", "Nam",
         "Sân chim tự nhiên giữa lòng thành phố"),
    "🌿 Bến Tre — Cồn Phụng":
        (10.33, 106.34, "thiên nhiên", "Bến Tre", "Nam",
         "Di tích đạo Dừa, du lịch cồn sông Tiền"),
    "🧵 Bến Tre — Làng dừa Bến Tre":
        (10.24, 106.38, "làng nghề", "Bến Tre", "Nam",
         "Xứ dừa, kẹo dừa, đi xuồng rạch dừa nước"),
    "🏖️ Cà Mau — Biển Khai Long":
        (8.65, 104.86, "biển", "Cà Mau", "Nam",
         "Bãi biển hoang sơ gần Đất Mũi"),
    "🏝️ Cà Mau — Hòn Đá Bạc":
        (9.093, 104.71, "đảo", "Cà Mau", "Nam",
         "Cụm đảo đá ven bờ, di tích chuyên án CM12"),
    "🏞️ Cà Mau — Mũi Cà Mau (Mốc GPS0001)":
        (8.6231, 104.71, "danh thắng", "Cà Mau", "Nam",
         "Điểm cực Nam Tổ quốc, mốc tọa độ quốc gia GPS0001"),
    "🌿 Cà Mau — Vườn quốc gia Mũi Cà Mau":
        (8.675, 104.7917, "thiên nhiên", "Cà Mau", "Nam",
         "Rừng ngập mặn, khu Ramsar, đất biết nở rừng biết đi"),
    "🌿 Cà Mau — Vườn quốc gia U Minh Hạ":
        (9.26, 104.95, "thiên nhiên", "Cà Mau", "Nam",
         "Rừng tràm ngập phèn, hệ sinh thái đặc trưng"),
    "💧 Cà Mau — Đầm Thị Tường":
        (9.05, 104.9, "hồ", "Cà Mau", "Nam",
         "Đầm nước tự nhiên lớn nhất ĐBSCL"),
    "🏞️ Cần Thơ — Bến Ninh Kiều":
        (10.033, 105.79, "danh thắng", "Cần Thơ", "Nam",
         "Bến sông biểu tượng, cầu đi bộ, du thuyền"),
    "🛍️ Cần Thơ — Chợ nổi Cái Răng":
        (10.011, 105.777, "chợ", "Cần Thơ", "Nam",
         "Chợ nổi lớn nhất miền Tây, di sản phi vật thể QG"),
    "🎡 Cần Thơ — Làng du lịch Mỹ Khánh":
        (10.01, 105.7, "vui chơi", "Cần Thơ", "Nam",
         "Vườn sinh thái, nhà cổ, đua heo"),
    "🏛️ Cần Thơ — Nhà cổ Bình Thủy":
        (10.067, 105.737, "di tích", "Cần Thơ", "Nam",
         "Nhà cổ Pháp-Việt, bối cảnh phim Người tình"),
    "🌿 Cần Thơ — Vườn cò Bằng Lăng":
        (10.14, 105.53, "thiên nhiên", "Cần Thơ", "Nam",
         "Sân cò lớn ở Thốt Nốt"),
    "🛍️ Hậu Giang — Chợ nổi Ngã Bảy (Phụng Hiệp)":
        (9.814, 105.82, "chợ", "Hậu Giang", "Nam",
         "Chợ nổi lịch sử nơi bảy nhánh sông gặp nhau"),
    "🌿 Hậu Giang — Khu bảo tồn Lung Ngọc Hoàng":
        (9.63, 105.63, "thiên nhiên", "Hậu Giang", "Nam",
         "Lá phổi xanh ĐBSCL, đất ngập nước"),
    "🏝️ Kiên Giang — Hòn Chông / Hòn Phụ Tử":
        (10.22, 104.64, "đảo", "Kiên Giang", "Nam",
         "Chùa Hang, Hòn Phụ Tử biểu tượng Kiên Giang"),
    "🏖️ Kiên Giang — Mũi Nai Hà Tiên":
        (10.372, 104.45, "biển", "Kiên Giang", "Nam",
         "Bãi biển cát nâu, hải đăng"),
    "🏖️ Kiên Giang — Phú Quốc - Bãi Sao":
        (10.045, 104.028, "biển", "Kiên Giang", "Nam",
         "Bãi biển cát trắng đẹp nhất đảo ngọc"),
    "🏖️ Kiên Giang — Phú Quốc - Bãi Trường":
        (10.17, 103.97, "biển", "Kiên Giang", "Nam",
         "Bãi biển dài nhất Phú Quốc, resort dày đặc"),
    "🏞️ Kiên Giang — Phú Quốc - Dinh Cậu":
        (10.2295, 103.9585, "danh thắng", "Kiên Giang", "Nam",
         "Biểu tượng đảo, hoàng hôn, chợ đêm"),
    "🌃 Kiên Giang — Phú Quốc - Dương Đông":
        (10.217, 103.96, "phố đêm", "Kiên Giang", "Nam",
         "Trung tâm đảo, chợ đêm, Dinh Cậu"),
    "🏝️ Kiên Giang — Phú Quốc - Hòn Thơm":
        (9.97, 104.015, "đảo", "Kiên Giang", "Nam",
         "Cáp treo vượt biển dài nhất thế giới"),
    "🎡 Kiên Giang — Phú Quốc - VinWonders":
        (10.3133, 103.8594, "vui chơi", "Kiên Giang", "Nam",
         "Khu vui chơi tổng hợp, công viên nước, safari"),
    "🕳️ Kiên Giang — Thạch Động Hà Tiên":
        (10.402, 104.47, "hang động", "Kiên Giang", "Nam",
         "Động đá vôi gắn truyền thuyết Thạch Sanh"),
    "🌿 Long An — Làng nổi Tân Lập":
        (10.77, 106.1, "thiên nhiên", "Long An", "Nam",
         "Rừng tràm ngập nước, đường xuyên rừng"),
    "🛕 Sóc Trăng — Chùa Dơi (Mahatup)":
        (9.582, 105.975, "chùa đền", "Sóc Trăng", "Nam",
         "Chùa Khmer cổ, đàn dơi quạ khổng lồ"),
    "🛕 Sóc Trăng — Chùa Kh'leang":
        (9.602, 105.969, "chùa đền", "Sóc Trăng", "Nam",
         "Chùa Khmer cổ nhất Sóc Trăng"),
    "🛕 Sóc Trăng — Chùa Đất Sét (Bửu Sơn Tự)":
        (9.6, 105.972, "chùa đền", "Sóc Trăng", "Nam",
         "Tượng và nến bằng đất sét độc đáo"),
    "🛍️ Sóc Trăng — Chợ nổi Ngã Năm":
        (9.572, 105.635, "chợ", "Sóc Trăng", "Nam",
         "Chợ nổi giao 5 nhánh sông"),
    "🎡 TP.HCM — Bitexco Financial Tower":
        (10.7717, 106.7043, "vui chơi", "TP.HCM", "Nam",
         "Tháp búp sen, Saigon Skydeck"),
    "🏛️ TP.HCM — Bưu điện Trung tâm Sài Gòn":
        (10.7799, 106.6999, "di tích", "TP.HCM", "Nam",
         "Bưu điện cổ do Pháp xây"),
    "🏛️ TP.HCM — Bảo tàng Chứng tích Chiến tranh":
        (10.7793, 106.6922, "di tích", "TP.HCM", "Nam",
         "Trưng bày hiện vật chiến tranh Việt Nam"),
    "🏛️ TP.HCM — Bảo tàng Mỹ thuật TP.HCM":
        (10.774, 106.698, "di tích", "TP.HCM", "Nam",
         "Dinh thự Pháp cổ, bộ sưu tập mỹ thuật VN"),
    "🛍️ TP.HCM — Chợ Bến Thành":
        (10.7724, 106.698, "chợ", "TP.HCM", "Nam",
         "Chợ biểu tượng Sài Gòn, cửa Nam"),
    "🛍️ TP.HCM — Chợ Lớn (Bình Tây)":
        (10.75, 106.651, "chợ", "TP.HCM", "Nam",
         "Khu người Hoa, chợ Bình Tây, ẩm thực"),
    "🎡 TP.HCM — Công viên Đầm Sen":
        (10.767, 106.636, "vui chơi", "TP.HCM", "Nam",
         "Công viên giải trí nước và trên cạn"),
    "🏛️ TP.HCM — Dinh Độc Lập":
        (10.777, 106.6958, "di tích", "TP.HCM", "Nam",
         "Dinh tổng thống VNCH, di tích quốc gia đặc biệt"),
    "🎡 TP.HCM — Khu du lịch Suối Tiên":
        (10.868, 106.802, "vui chơi", "TP.HCM", "Nam",
         "Công viên chủ đề văn hóa tâm linh"),
    "🍜 TP.HCM — Khu đô thị Thảo Điền":
        (10.803, 106.737, "ăn uống", "TP.HCM", "Nam",
         "Khu bar, cafe, nhà hàng Tây Quận 2"),
    "🎡 TP.HCM — Landmark 81":
        (10.795, 106.7218, "vui chơi", "TP.HCM", "Nam",
         "Tòa nhà cao nhất Việt Nam, đài quan sát"),
    "🍜 TP.HCM — Làng gốm Bát Tràng (HN) - Phố đặc sản SG":
        (10.774, 106.699, "ăn uống", "TP.HCM", "Nam",
         "Khu ẩm thực Q1, bún mắm, cơm tấm, hủ tiếu"),
    "🏛️ TP.HCM — Nhà thờ Đức Bà Sài Gòn":
        (10.7797, 106.699, "di tích", "TP.HCM", "Nam",
         "Nhà thờ chính tòa gạch đỏ kiến trúc Pháp"),
    "🌃 TP.HCM — Phố Tây Bùi Viện":
        (10.767, 106.693, "phố đêm", "TP.HCM", "Nam",
         "Phố bar Tây balo sôi động"),
    "🌃 TP.HCM — Phố đi bộ Nguyễn Huệ":
        (10.774, 106.704, "phố đêm", "TP.HCM", "Nam",
         "Quảng trường đi bộ, tượng đài Bác Hồ"),
    "🍜 TP.HCM — Phố ẩm thực Vĩnh Khánh":
        (10.759, 106.696, "ăn uống", "TP.HCM", "Nam",
         "Phố ốc và hải sản Quận 4"),
    "🎡 TP.HCM — Thảo Cầm Viên Sài Gòn":
        (10.7877, 106.705, "vui chơi", "TP.HCM", "Nam",
         "Sở thú lâu đời nhất Việt Nam"),
    "🏛️ TP.HCM — Địa đạo Củ Chi":
        (11.144, 106.464, "di tích", "TP.HCM", "Nam",
         "Hệ thống địa đạo kháng chiến nổi tiếng"),
    "🏖️ Tiền Giang — Biển Tân Thành Gò Công":
        (10.31, 106.77, "biển", "Tiền Giang", "Nam",
         "Bãi biển cát đen, nghêu, cào ốc"),
    "🛍️ Tiền Giang — Chợ nổi Cái Bè":
        (10.35, 106.04, "chợ", "Tiền Giang", "Nam",
         "Chợ nổi lâu đời trên sông Tiền"),
    "🌿 Tiền Giang — Cù lao Thới Sơn (cồn Lân)":
        (10.34, 106.36, "thiên nhiên", "Tiền Giang", "Nam",
         "Cù lao miệt vườn, đờn ca tài tử, mật ong"),
    "🍜 Tiền Giang — Mỹ Tho (ăn uống)":
        (10.3597, 106.3655, "ăn uống", "Tiền Giang", "Nam",
         "Hũ tiếu Mỹ Tho chính gốc, đặc sản sông nước"),
    "💧 Trà Vinh — Ao Bà Om":
        (9.921, 106.342, "hồ", "Trà Vinh", "Nam",
         "Ao thiêng rừng cổ thụ rễ nổi"),
    "🏖️ Trà Vinh — Biển Ba Động":
        (9.777, 106.523, "biển", "Trà Vinh", "Nam",
         "Bãi biển cát đen, gần đặc sản dừa sáp Cầu Kè"),
    "🛕 Trà Vinh — Chùa Âng":
        (9.92, 106.345, "chùa đền", "Trà Vinh", "Nam",
         "Chùa Khmer cổ trong ao Bà Om"),
    "🌿 Trà Vinh — Cồn Chim Trà Vinh":
        (9.85, 106.45, "thiên nhiên", "Trà Vinh", "Nam",
         "Cồn xanh giữa sông, du lịch sinh thái"),
    "💧 Tây Ninh — Hồ Dầu Tiếng":
        (11.28, 106.33, "hồ", "Tây Ninh", "Nam",
         "Hồ thủy lợi nhân tạo lớn nhất Việt Nam"),
    "⛰️ Tây Ninh — Núi Bà Đen":
        (11.383, 106.172, "núi", "Tây Ninh", "Nam",
         "Nóc nhà Nam Bộ 986m, cáp treo, chùa Bà"),
    "🛕 Tây Ninh — Tòa thánh Cao Đài Tây Ninh":
        (11.305, 106.137, "chùa đền", "Tây Ninh", "Nam",
         "Thánh thất Cao Đài lớn nhất, kiến trúc độc đáo"),
    "🌿 Tây Ninh — VQG Lò Gò - Xa Mát":
        (11.65, 105.95, "thiên nhiên", "Tây Ninh", "Nam",
         "Rừng biên giới, đa dạng chim"),
    "🌿 Vĩnh Long — Cù lao An Bình":
        (10.25, 105.98, "thiên nhiên", "Vĩnh Long", "Nam",
         "Cù lao vườn trái cây, homestay sông nước"),
    "🧵 Vĩnh Long — Làng hoa Chợ Lách":
        (10.22, 106.14, "làng nghề", "Vĩnh Long", "Nam",
         "Làng hoa cây cảnh, mai vàng Tết"),
    "🏛️ Vĩnh Long — Văn Thánh Miếu Vĩnh Long":
        (10.245, 105.965, "di tích", "Vĩnh Long", "Nam",
         "Văn miếu cổ Nam Bộ"),
    "🏛️ Vũng Tàu — Bạch Dinh (Villa Blanche)":
        (10.348, 107.0764, "di tích", "Vũng Tàu", "Nam",
         "Dinh thự Pháp cổ thế kỷ 19, bảo tàng đồ sứ"),
    "🏖️ Vũng Tàu — Long Hải":
        (10.47, 107.31, "biển", "Vũng Tàu", "Nam",
         "Bãi biển cô đơn, ít đông, cá tươi"),
    "💧 Đồng Nai — Hồ Trị An":
        (11.1, 107.04, "hồ", "Đồng Nai", "Nam",
         "Hồ thủy điện, đảo Ó, câu cá"),
    "💦 Đồng Nai — Thác Giang Điền":
        (10.945, 107.03, "thác", "Đồng Nai", "Nam",
         "Thác và khu dã ngoại gần Biên Hòa"),
    "🌿 Đồng Nai — Vườn quốc gia Cát Tiên":
        (11.42, 107.43, "thiên nhiên", "Đồng Nai", "Nam",
         "Rừng nhiệt đới, khu dự trữ sinh quyển, Bàu Sấu"),
    "🏛️ Đồng Tháp — Khu di tích Nguyễn Sinh Sắc":
        (10.456, 105.635, "di tích", "Đồng Tháp", "Nam",
         "Mộ cụ Phó bảng thân sinh Chủ tịch Hồ Chí Minh"),
    "🌿 Đồng Tháp — Khu sinh thái Gáo Giồng":
        (10.65, 105.59, "thiên nhiên", "Đồng Tháp", "Nam",
         "Rừng tràm, sân chim, đi xuồng ba lá"),
    "🧵 Đồng Tháp — Làng hoa Sa Đéc":
        (10.296, 105.748, "làng nghề", "Đồng Tháp", "Nam",
         "Làng hoa kiểng lớn nhất miền Tây"),
    "🌿 Đồng Tháp — Vườn quốc gia Tràm Chim":
        (10.72, 105.56, "thiên nhiên", "Đồng Tháp", "Nam",
         "Khu Ramsar, sếu đầu đỏ, sen mùa nước nổi"),

    # ── Tây Nguyên (26 điểm) ──
    "💧 Gia Lai — Biển Hồ (T'Nưng) Pleiku":
        (14.0398, 107.9997, "hồ", "Gia Lai", "Tây Nguyên",
         "Hồ miệng núi lửa, đôi mắt Pleiku"),
    "🛕 Gia Lai — Chùa Minh Thành Pleiku":
        (13.97, 108.0, "chùa đền", "Gia Lai", "Tây Nguyên",
         "Chùa kiến trúc Nhật-Đài độc đáo"),
    "💦 Gia Lai — Thác Phú Cường":
        (13.68, 108.1, "thác", "Gia Lai", "Tây Nguyên",
         "Thác trên nền đá bazan, Chư Sê (gần đúng)"),
    "🏞️ Kon Tum — Cầu treo Kon Klor":
        (14.352, 108.023, "danh thắng", "Kon Tum", "Tây Nguyên",
         "Cầu treo dây văng qua sông Đăk Bla (gần đúng)"),
    "🌿 Kon Tum — Măng Đen":
        (14.64, 108.29, "thiên nhiên", "Kon Tum", "Tây Nguyên",
         "Đà Lạt thứ 2, rừng thông, thác Pa Sỹ, hồ Đăk Ke"),
    "🏞️ Kon Tum — Ngã ba Đông Dương":
        (14.695, 107.545, "danh thắng", "Kon Tum", "Tây Nguyên",
         "Cột mốc biên giới Việt-Lào-Campuchia (gần đúng)"),
    "🛕 Kon Tum — Nhà thờ gỗ Kon Tum":
        (14.354, 107.999, "chùa đền", "Kon Tum", "Tây Nguyên",
         "Nhà thờ gỗ trăm tuổi kiến trúc Roman-Bana"),
    "🌃 Lâm Đồng — Chợ đêm Đà Lạt":
        (11.946, 108.437, "phố đêm", "Lâm Đồng", "Tây Nguyên",
         "Chợ Âm Phủ, ẩm thực đêm, đồ len"),
    "💧 Lâm Đồng — Hồ Tuyền Lâm":
        (11.91, 108.43, "hồ", "Lâm Đồng", "Tây Nguyên",
         "Hồ lớn Đà Lạt, Thiền viện Trúc Lâm"),
    "💧 Lâm Đồng — Hồ Xuân Hương Đà Lạt":
        (11.942, 108.439, "hồ", "Lâm Đồng", "Tây Nguyên",
         "Hồ trung tâm thành phố ngàn hoa"),
    "⛰️ Lâm Đồng — Núi Langbiang":
        (12.048, 108.442, "núi", "Lâm Đồng", "Tây Nguyên",
         "Nóc nhà Đà Lạt, truyền thuyết K'Lang-Hơ Biang"),
    "🏞️ Lâm Đồng — Thung lũng Tình Yêu":
        (11.97, 108.45, "danh thắng", "Lâm Đồng", "Tây Nguyên",
         "Thung lũng hồ Đa Thiện, đồi thông"),
    "💦 Lâm Đồng — Thác Dambri":
        (11.573, 107.76, "thác", "Lâm Đồng", "Tây Nguyên",
         "Thác cao nhất Lâm Đồng, Bảo Lộc (gần đúng)"),
    "💦 Lâm Đồng — Thác Datanla":
        (11.9, 108.44, "thác", "Lâm Đồng", "Tây Nguyên",
         "Thác gần đèo Prenn, máng trượt"),
    "💦 Lâm Đồng — Thác Pongour":
        (11.6888, 108.2658, "thác", "Lâm Đồng", "Tây Nguyên",
         "Nam thiên đệ nhất thác, 7 tầng, sông Đa Nhim, Đức Trọng"),
    "🏞️ Lâm Đồng — Vườn hoa thành phố Đà Lạt":
        (11.95, 108.444, "danh thắng", "Lâm Đồng", "Tây Nguyên",
         "Vườn hoa lớn bên hồ Xuân Hương"),
    "🏞️ Lâm Đồng — Đèo Prenn":
        (11.89, 108.43, "danh thắng", "Lâm Đồng", "Tây Nguyên",
         "Cửa ngõ vào Đà Lạt, thông rừng"),
    "🏞️ Lâm Đồng — Đồi chè Cầu Đất":
        (11.85, 108.5167, "danh thắng", "Lâm Đồng", "Tây Nguyên",
         "Đồi chè xanh ngát, check-in sunrise"),
    "🏘️ Đắk Lắk — Buôn Akô Dhông":
        (12.69, 108.07, "làng bản dân tộc", "Đắk Lắk", "Tây Nguyên",
         "Làng cà phê Ê Đê, nhà dài, văn hóa cồng chiêng"),
    "🌃 Đắk Lắk — Buôn Ma Thuột (trung tâm)":
        (12.6667, 108.05, "phố đêm", "Đắk Lắk", "Tây Nguyên",
         "Thủ phủ cà phê, ngã sáu, bảo tàng"),
    "💧 Đắk Lắk — Hồ Lắk":
        (12.4225, 108.18, "hồ", "Đắk Lắk", "Tây Nguyên",
         "Hồ nước ngọt tự nhiên lớn, cưỡi voi, buôn Jun"),
    "💦 Đắk Lắk — Thác Dray Nur":
        (12.534, 107.887, "thác", "Đắk Lắk", "Tây Nguyên",
         "Thác vợ hùng vĩ trên sông Sêrêpốk (gần đúng)"),
    "🌿 Đắk Lắk — VQG Yok Đôn":
        (12.8038, 107.6707, "thiên nhiên", "Đắk Lắk", "Tây Nguyên",
         "Rừng khộp lớn nhất, voi hoang dã"),
    "🌿 Đắk Nông — Công viên địa chất Đắk Nông":
        (12.27, 107.69, "thiên nhiên", "Đắk Nông", "Tây Nguyên",
         "Công viên địa chất toàn cầu UNESCO, hang núi lửa"),
    "💧 Đắk Nông — Hồ Tà Đùng":
        (11.95, 107.9, "hồ", "Đắk Nông", "Tây Nguyên",
         "Vịnh Hạ Long Tây Nguyên, 36 đảo nhỏ (gần đúng)"),
    "💦 Đắk Nông — Thác Dray Sáp":
        (12.5395, 107.8865, "thác", "Đắk Nông", "Tây Nguyên",
         "Thác chồng khói nước, sông Sêrêpốk"),

    # ── Trung (98 điểm) ──
    "🏞️ Bình Thuận (cũ) — Bàu Trắng (Bàu Sen)":
        (11.19, 108.42, "danh thắng", "Bình Thuận (cũ)", "Trung",
         "Hồ sen giữa đồi cát trắng, tiểu sa mạc"),
    "🛕 Bình Thuận (cũ) — Chùa núi Tà Cú":
        (10.77, 107.85, "chùa đền", "Bình Thuận (cũ)", "Trung",
         "Tượng Phật nằm dài 49m, cáp treo"),
    "🏖️ Bình Thuận (cũ) — Mũi Kê Gà":
        (10.69, 107.99, "biển", "Bình Thuận (cũ)", "Trung",
         "Hải đăng cổ nhất Việt Nam trên đảo nhỏ"),
    "🌿 Bình Thuận (cũ) — Suối Tiên Mũi Né":
        (10.95, 108.26, "thiên nhiên", "Bình Thuận (cũ)", "Trung",
         "Khe suối chảy qua vách cát đỏ"),
    "🏝️ Bình Thuận (cũ) — Đảo Phú Quý":
        (10.52, 108.94, "đảo", "Bình Thuận (cũ)", "Trung",
         "Đảo hoang sơ ngoài khơi Phan Thiết"),
    "🏞️ Bình Thuận (cũ) — Đồi cát bay Mũi Né":
        (10.943, 108.295, "danh thắng", "Bình Thuận (cũ)", "Trung",
         "Đồi cát vàng-hồng đổi hình theo gió"),
    "🏝️ Bình Định — Đảo Nhơn Châu":
        (13.65, 109.36, "đảo", "Bình Định", "Trung",
         "Đảo nhỏ gần Quy Nhơn, nước trong, ít khách"),
    "🏞️ Bình Định (cũ) — Eo Gió":
        (13.79, 109.345, "danh thắng", "Bình Định (cũ)", "Trung",
         "Eo biển ngắm hoàng hôn, Nhơn Lý"),
    "🏖️ Bình Định (cũ) — Kỳ Co":
        (13.76, 109.355, "biển", "Bình Định (cũ)", "Trung",
         "Bãi biển Maldives Việt Nam, nước xanh ngọc"),
    "🏖️ Bình Định (cũ) — Quy Nhơn - biển trung tâm":
        (13.77, 109.234, "biển", "Bình Định (cũ)", "Trung",
         "Bãi biển thành phố, đường Xuân Diệu"),
    "🏛️ Bình Định (cũ) — Tháp Bánh Ít":
        (13.87, 109.11, "di tích", "Bình Định (cũ)", "Trung",
         "Cụm tháp Chăm trên đồi"),
    "🏛️ Bình Định (cũ) — Tháp Đôi Quy Nhơn":
        (13.777, 109.216, "di tích", "Bình Định (cũ)", "Trung",
         "Tháp Chăm đôi trong thành phố"),
    "🏘️ Huế — A Lưới - văn hóa dân tộc":
        (16.25, 107.26, "làng bản dân tộc", "Huế", "Trung",
         "Đường mòn HCM, văn hóa Pa Kô, Tà Ôi"),
    "🏖️ Huế — Biển Lăng Cô":
        (16.251, 108.073, "biển", "Huế", "Trung",
         "Vịnh biển đẹp dưới chân đèo Hải Vân"),
    "🏖️ Huế — Biển Thuận An":
        (16.571, 107.635, "biển", "Huế", "Trung",
         "Bãi biển cửa phá gần Huế (gần đúng)"),
    "🍜 Huế — Bún bò Huế - khu Đông Ba":
        (16.4692, 107.595, "ăn uống", "Huế", "Trung",
         "Bún bò cay nồng sả thơm, chả lụa Huế"),
    "⛰️ Huế — Bạch Mã":
        (16.21, 107.86, "núi", "Huế", "Trung",
         "VQG, thác Đỗ Quyên, đỉnh mây mù 1450m"),
    "🛕 Huế — Chùa Thiên Mụ":
        (16.4536, 107.5448, "chùa đền", "Huế", "Trung",
         "Chùa biểu tượng Huế, tháp Phước Duyên sông Hương"),
    "🏞️ Huế — Cầu Trường Tiền":
        (16.4689, 107.5886, "danh thắng", "Huế", "Trung",
         "Cầu sắt cổ bắc qua sông Hương"),
    "🏛️ Huế — Lăng Gia Long":
        (16.3667, 107.545, "di tích", "Huế", "Trung",
         "Lăng vua đầu triều Nguyễn (gần đúng)"),
    "🏛️ Huế — Lăng Khải Định":
        (16.3989, 107.5903, "di tích", "Huế", "Trung",
         "Lăng vua Khải Định, khảm sành kiến trúc Đông-Tây"),
    "🏛️ Huế — Lăng Minh Mạng":
        (16.3878, 107.5678, "di tích", "Huế", "Trung",
         "Lăng vua Minh Mạng, bố cục đối xứng"),
    "🏛️ Huế — Lăng Thiệu Trị":
        (16.436, 107.556, "di tích", "Huế", "Trung",
         "Lăng vua Thiệu Trị (gần đúng)"),
    "🏛️ Huế — Lăng Tự Đức":
        (16.4574, 107.5533, "di tích", "Huế", "Trung",
         "Lăng vua Tự Đức, hồ sen thơ mộng (gần đúng)"),
    "🏛️ Huế — Lăng Đồng Khánh":
        (16.447, 107.562, "di tích", "Huế", "Trung",
         "Lăng vua Đồng Khánh (gần đúng)"),
    "🏛️ Huế — Đại Nội Huế (Hoàng thành)":
        (16.4697, 107.5778, "di tích", "Huế", "Trung",
         "Kinh thành triều Nguyễn, di sản UNESCO"),
    "🌿 Huế — Đầm phá Tam Giang":
        (16.56, 107.6318, "thiên nhiên", "Huế", "Trung",
         "Hệ đầm phá lớn nhất Đông Nam Á, hoàng hôn"),
    "🏞️ Huế — Đồi Vọng Cảnh":
        (16.438, 107.556, "danh thắng", "Huế", "Trung",
         "Đồi ngắm sông Hương (gần đúng)"),
    "🏖️ Hà Tĩnh — Biển Thiên Cầm":
        (18.2, 106.18, "biển", "Hà Tĩnh", "Trung",
         "Bãi biển đẹp, truyền thuyết đàn trời"),
    "🏖️ Hà Tĩnh — Biển Xuân Thành":
        (18.25, 106.09, "biển", "Hà Tĩnh", "Trung",
         "Bãi biển hoang sơ, ít du khách"),
    "🛕 Hà Tĩnh — Chùa Hương Tích Hà Tĩnh":
        (18.36, 105.71, "chùa đền", "Hà Tĩnh", "Trung",
         "Hoan Châu đệ nhất danh lam trên núi Hồng Lĩnh"),
    "🏛️ Hà Tĩnh — Ngã ba Đồng Lộc":
        (18.49, 105.63, "di tích", "Hà Tĩnh", "Trung",
         "Di tích 10 nữ TNXP, đường Trường Sơn"),
    "🏞️ Hà Tĩnh — Đèo Ngang":
        (17.9, 106.47, "danh thắng", "Hà Tĩnh", "Trung",
         "Đèo ranh giới lịch sử, Hoành Sơn Quan"),
    "🏖️ Khánh Hòa — Cam Ranh - Bãi Dài":
        (12.0, 109.17, "biển", "Khánh Hòa", "Trung",
         "Bãi biển resort cao cấp, nước xanh ngọc"),
    "🛍️ Khánh Hòa — Chợ đêm Nha Trang":
        (12.25, 109.2, "chợ", "Khánh Hòa", "Trung",
         "Hải sản nướng, bar phố, về đêm sầm uất"),
    "🏖️ Khánh Hòa — Nha Trang - biển Trần Phú":
        (12.24, 109.196, "biển", "Khánh Hòa", "Trung",
         "Bãi biển trung tâm thành phố"),
    "🏛️ Khánh Hòa — Tháp Bà Ponagar":
        (12.265, 109.195, "di tích", "Khánh Hòa", "Trung",
         "Quần thể tháp Chăm thờ Thiên Y Ana"),
    "🎡 Khánh Hòa — Vinpearl Hòn Tre":
        (12.213, 109.245, "vui chơi", "Khánh Hòa", "Trung",
         "Đảo giải trí, cáp treo vượt biển"),
    "🏖️ Khánh Hòa — Vịnh Vân Phong":
        (12.55, 109.25, "biển", "Khánh Hòa", "Trung",
         "Vịnh biển rộng lớn, hoang sơ, lặn biển"),
    "🏝️ Khánh Hòa — Đảo Bình Ba":
        (11.82, 109.22, "đảo", "Khánh Hòa", "Trung",
         "Đảo tôm hùm ở vịnh Cam Ranh"),
    "🏝️ Khánh Hòa — Đảo Bình Hưng":
        (11.77, 109.25, "đảo", "Khánh Hòa", "Trung",
         "Đảo nhỏ nước trong, hải sản"),
    "🏖️ Nghệ An — Biển Cửa Hội":
        (18.82, 105.74, "biển", "Nghệ An", "Trung",
         "Cửa sông Lam, hải sản, chợ đêm"),
    "🏖️ Nghệ An — Biển Cửa Lò":
        (18.8, 105.71, "biển", "Nghệ An", "Trung",
         "Bãi biển du lịch nổi tiếng Bắc Trung Bộ"),
    "🏛️ Nghệ An — Làng Sen (quê Bác)":
        (18.678, 105.515, "di tích", "Nghệ An", "Trung",
         "Quê hương Chủ tịch Hồ Chí Minh, Kim Liên"),
    "🌿 Nghệ An — VQG Pù Mát":
        (18.95, 104.75, "thiên nhiên", "Nghệ An", "Trung",
         "Rừng nguyên sinh Con Cuông, thác Kèm"),
    "🏖️ Ninh Thuận (cũ) — Biển Ninh Chữ":
        (11.58, 109.03, "biển", "Ninh Thuận (cũ)", "Trung",
         "Bãi biển hiền hòa gần Phan Rang"),
    "🧵 Ninh Thuận (cũ) — Làng gốm Bàu Trúc":
        (11.55, 108.93, "làng nghề", "Ninh Thuận (cũ)", "Trung",
         "Làng gốm Chăm cổ nhất Đông Nam Á"),
    "🏖️ Ninh Thuận (cũ) — Mũi Dinh":
        (11.37, 109.01, "biển", "Ninh Thuận (cũ)", "Trung",
         "Đồi cát và hải đăng, khung cảnh sa mạc"),
    "🏛️ Ninh Thuận (cũ) — Tháp Pô Klong Garai":
        (11.585, 108.97, "di tích", "Ninh Thuận (cũ)", "Trung",
         "Cụm tháp Chăm trên đồi Trầu, thế kỷ 13"),
    "🌿 Ninh Thuận (cũ) — Vườn nho Thái An":
        (11.68, 109.17, "thiên nhiên", "Ninh Thuận (cũ)", "Trung",
         "Vườn nho, cừu, check-in ven biển"),
    "🏖️ Ninh Thuận (cũ) — Vịnh Vĩnh Hy":
        (11.71, 109.19, "biển", "Ninh Thuận (cũ)", "Trung",
         "Vịnh đẹp trong VQG Núi Chúa, san hô"),
    "💧 Phú Yên — Đầm Ô Loan":
        (13.38, 109.26, "hồ", "Phú Yên", "Trung",
         "Đầm phá đẹp, sò huyết, cua ghẹ"),
    "🏖️ Phú Yên (cũ) — Bãi Xép":
        (13.26, 109.29, "biển", "Phú Yên (cũ)", "Trung",
         "Bối cảnh phim Tôi thấy hoa vàng trên cỏ xanh"),
    "🏞️ Phú Yên (cũ) — Gành Đá Đĩa":
        (13.335, 109.2981, "danh thắng", "Phú Yên (cũ)", "Trung",
         "Cột đá bazan lục lăng, Di tích QG đặc biệt 2020"),
    "🏞️ Phú Yên (cũ) — Mũi Điện (Đại Lãnh)":
        (12.885, 109.456, "danh thắng", "Phú Yên (cũ)", "Trung",
         "Điểm đón bình minh sớm nhất đất liền, hải đăng"),
    "🏛️ Phú Yên (cũ) — Tháp Nhạn":
        (13.09, 109.305, "di tích", "Phú Yên (cũ)", "Trung",
         "Tháp Chăm trên núi Nhạn, Tuy Hòa"),
    "🏖️ Phú Yên (cũ) — Vịnh Xuân Đài":
        (13.47, 109.27, "biển", "Phú Yên (cũ)", "Trung",
         "Vịnh đẹp, nuôi tôm hùm, Sông Cầu"),
    "🏛️ Quảng Bình — Vũng Chùa - mộ Đại tướng":
        (17.97, 106.48, "di tích", "Quảng Bình", "Trung",
         "Nơi an nghỉ Đại tướng Võ Nguyên Giáp"),
    "🏖️ Quảng Bình (cũ) — Biển Nhật Lệ Đồng Hới":
        (17.475, 106.625, "biển", "Quảng Bình (cũ)", "Trung",
         "Bãi biển thành phố Đồng Hới"),
    "🕳️ Quảng Bình (cũ) — Hang Sơn Đoòng":
        (17.4569, 106.2875, "hang động", "Quảng Bình (cũ)", "Trung",
         "Hang tự nhiên lớn nhất thế giới (Guinness 2013)"),
    "🌿 Quảng Bình (cũ) — Suối Nước Moọc":
        (17.54, 106.27, "thiên nhiên", "Quảng Bình (cũ)", "Trung",
         "Suối nước xanh trong VQG Phong Nha"),
    "🏖️ Quảng Bình (cũ) — Đá Nhảy":
        (17.63, 106.47, "biển", "Quảng Bình (cũ)", "Trung",
         "Bãi biển đá kỳ thú dưới đèo Lý Hòa"),
    "🕳️ Quảng Bình (cũ) — Động Phong Nha":
        (17.58, 106.283, "hang động", "Quảng Bình (cũ)", "Trung",
         "Động nước, sông ngầm, di sản UNESCO"),
    "🕳️ Quảng Bình (cũ) — Động Thiên Đường":
        (17.52, 106.25, "hang động", "Quảng Bình (cũ)", "Trung",
         "Động khô dài, hệ thạch nhũ hoàng cung"),
    "🍜 Quảng Nam — Bánh mì Phượng Hội An":
        (15.8769, 108.3283, "ăn uống", "Quảng Nam", "Trung",
         "Bánh mì ngon nhất thế giới (Anthony Bourdain)"),
    "🧵 Quảng Nam — Làng mộc Kim Bồng":
        (15.87, 108.36, "làng nghề", "Quảng Nam", "Trung",
         "Làng nghề mộc truyền thống Hội An"),
    "🏝️ Quảng Nam (cũ) — Cù Lao Chàm":
        (15.952, 108.517, "đảo", "Quảng Nam (cũ)", "Trung",
         "Khu dự trữ sinh quyển, lặn san hô"),
    "🧵 Quảng Nam (cũ) — Làng gốm Thanh Hà":
        (15.878, 108.31, "làng nghề", "Quảng Nam (cũ)", "Trung",
         "Làng gốm 500 năm ven sông Thu Bồn"),
    "🧵 Quảng Nam (cũ) — Làng rau Trà Quế":
        (15.905, 108.335, "làng nghề", "Quảng Nam (cũ)", "Trung",
         "Làng rau hữu cơ truyền thống gần Hội An"),
    "🏛️ Quảng Nam (cũ) — Phố cổ Hội An":
        (15.88, 108.328, "di tích", "Quảng Nam (cũ)", "Trung",
         "Đô thị cổ UNESCO, chùa Cầu, đèn lồng"),
    "🌿 Quảng Nam (cũ) — Rừng dừa Bảy Mẫu":
        (15.885, 108.36, "thiên nhiên", "Quảng Nam (cũ)", "Trung",
         "Rừng dừa nước, thuyền thúng"),
    "🏛️ Quảng Nam (cũ) — Thánh địa Mỹ Sơn":
        (15.764, 108.124, "di tích", "Quảng Nam (cũ)", "Trung",
         "Quần thể đền tháp Chăm UNESCO"),
    "🏖️ Quảng Ngãi — Biển Mỹ Khê Quảng Ngãi":
        (15.15, 108.92, "biển", "Quảng Ngãi", "Trung",
         "Bãi biển cát trắng phi lao"),
    "🏖️ Quảng Ngãi — Biển Sa Huỳnh":
        (14.68, 109.05, "biển", "Quảng Ngãi", "Trung",
         "Bãi biển và di chỉ văn hóa Sa Huỳnh"),
    "🏛️ Quảng Ngãi — Khu chứng tích Sơn Mỹ (Mỹ Lai)":
        (15.178, 108.87, "di tích", "Quảng Ngãi", "Trung",
         "Tưởng niệm vụ thảm sát Mỹ Lai 1968"),
    "🏝️ Quảng Ngãi — Đảo Lý Sơn":
        (15.383, 109.116, "đảo", "Quảng Ngãi", "Trung",
         "Đảo núi lửa, tỏi, cột cờ Thới Lới, Hang Câu"),
    "🏛️ Quảng Trị — Cầu Hiền Lương - vĩ tuyến 17":
        (17.0044, 107.0518, "di tích", "Quảng Trị", "Trung",
         "Giới tuyến chia cắt hai miền, sông Bến Hải"),
    "🏞️ Quảng Trị — Cửa khẩu Lao Bảo":
        (16.6167, 106.6, "danh thắng", "Quảng Trị", "Trung",
         "Cửa khẩu quốc tế biên giới Lào, QL9"),
    "🏛️ Quảng Trị — Khe Sanh (căn cứ Tà Cơn)":
        (16.6542, 106.7242, "di tích", "Quảng Trị", "Trung",
         "Chiến trường Khe Sanh 1968, Hướng Hóa"),
    "🏛️ Quảng Trị — Nghĩa trang liệt sĩ Trường Sơn":
        (16.9586, 106.9549, "di tích", "Quảng Trị", "Trung",
         "Nghĩa trang liệt sĩ lớn nhất Việt Nam"),
    "🏛️ Quảng Trị — Thành cổ Quảng Trị":
        (16.7469, 107.1944, "di tích", "Quảng Trị", "Trung",
         "Chiến địa 81 ngày đêm 1972"),
    "🏝️ Quảng Trị — Đảo Cồn Cỏ":
        (17.16, 107.34, "đảo", "Quảng Trị", "Trung",
         "Đảo tiền tiêu, du lịch sinh thái biển"),
    "🏛️ Quảng Trị — Địa đạo Vịnh Mốc":
        (17.0729, 107.1075, "di tích", "Quảng Trị", "Trung",
         "Địa đạo tránh bom Vĩnh Linh, ra tận biển"),
    "🏖️ Thanh Hóa — Biển Hải Tiến":
        (19.88, 105.95, "biển", "Thanh Hóa", "Trung",
         "Bãi biển mới phát triển Hoằng Hóa"),
    "🏖️ Thanh Hóa — Biển Sầm Sơn":
        (19.75, 105.905, "biển", "Thanh Hóa", "Trung",
         "Bãi biển nổi tiếng, Hòn Trống Mái"),
    "🏛️ Thanh Hóa — Khu di tích Lam Kinh":
        (19.92, 105.43, "di tích", "Thanh Hóa", "Trung",
         "Đất tổ nhà Lê, đền miếu cổ"),
    "🌿 Thanh Hóa — Pù Luông":
        (20.45, 105.17, "thiên nhiên", "Thanh Hóa", "Trung",
         "Khu bảo tồn, ruộng bậc thang, homestay"),
    "🌿 Thanh Hóa — Suối cá thần Cẩm Lương":
        (20.2415, 105.4682, "thiên nhiên", "Thanh Hóa", "Trung",
         "Đàn cá dốc (Sách đỏ), cá chúa tới 30 kg"),
    "🏛️ Thanh Hóa — Thành nhà Hồ":
        (20.077, 105.603, "di tích", "Thanh Hóa", "Trung",
         "Thành đá cổ triều Hồ, di sản UNESCO"),
    "🏖️ Đà Nẵng — Biển Mỹ Khê Đà Nẵng":
        (16.058, 108.247, "biển", "Đà Nẵng", "Trung",
         "Một trong những bãi biển quyến rũ nhất hành tinh"),
    "🏖️ Đà Nẵng — Biển Non Nước":
        (16.0, 108.265, "biển", "Đà Nẵng", "Trung",
         "Bãi biển làng đá mỹ nghệ Non Nước"),
    "🎡 Đà Nẵng — Bà Nà Hills":
        (15.995, 107.996, "vui chơi", "Đà Nẵng", "Trung",
         "Khu nghỉ dưỡng núi, Cầu Vàng, làng Pháp"),
    "🌿 Đà Nẵng — Bán đảo Sơn Trà":
        (16.105, 108.278, "thiên nhiên", "Đà Nẵng", "Trung",
         "Rừng, voọc chà vá chân nâu, chùa Linh Ứng"),
    "🏛️ Đà Nẵng — Bảo tàng Chăm Đà Nẵng":
        (16.054, 108.223, "di tích", "Đà Nẵng", "Trung",
         "Bộ sưu tập điêu khắc Chăm lớn nhất VN"),
    "🛍️ Đà Nẵng — Chợ Hàn":
        (16.07, 108.224, "chợ", "Đà Nẵng", "Trung",
         "Chợ trung tâm, đặc sản, ẩm thực"),
    "🏞️ Đà Nẵng — Cầu Rồng":
        (16.061, 108.227, "danh thắng", "Đà Nẵng", "Trung",
         "Cầu hình rồng phun lửa cuối tuần"),
    "⛰️ Đà Nẵng — Ngũ Hành Sơn":
        (16.004, 108.263, "núi", "Đà Nẵng", "Trung",
         "Năm ngọn núi đá vôi, hang động, chùa"),
    "🏞️ Đà Nẵng — Đèo Hải Vân":
        (16.198, 108.13, "danh thắng", "Đà Nẵng", "Trung",
         "Đèo biển hùng vĩ, Hải Vân Quan"),

    # ── Bắc (46 điểm) ──
    "🛕 Bắc Ninh — Chùa Bút Tháp":
        (21.05, 106.12, "chùa đền", "Bắc Ninh", "Bắc",
         "Chùa cổ, tượng Quan Âm nghìn mắt nghìn tay"),
    "🧵 Bắc Ninh — Làng tranh Đông Hồ":
        (21.05, 106.1, "làng nghề", "Bắc Ninh", "Bắc",
         "Làng tranh dân gian truyền thống"),
    "🏛️ Bắc Ninh — Đền Đô (Đình Bảng)":
        (21.12, 105.96, "di tích", "Bắc Ninh", "Bắc",
         "Đền thờ 8 vị vua triều Lý"),
    "🛕 Hà Nam — Chùa Tam Chúc":
        (20.42, 105.89, "chùa đền", "Hà Nam", "Bắc",
         "Quần thể chùa khổng lồ, hồ và núi"),
    "🌿 Hà Nam — Kẽm Trống Hà Nam":
        (20.55, 105.75, "thiên nhiên", "Hà Nam", "Bắc",
         "Hẻm sông qua núi đá vôi, thuyền thúng"),
    "🍜 Hà Nội — Bún chả Hương Liên":
        (21.0231, 105.8411, "ăn uống", "Hà Nội", "Bắc",
         "Bún chả Obama, Anthony Bourdain nổi tiếng"),
    "🏛️ Hà Nội — Bảo tàng Dân tộc học":
        (21.039, 105.822, "di tích", "Hà Nội", "Bắc",
         "Nhà sàn, nhà dài, nhà mồ các dân tộc VN"),
    "🛕 Hà Nội — Chùa Hương":
        (20.618, 105.748, "chùa đền", "Hà Nội", "Bắc",
         "Quần thể chùa hang, lễ hội xuân, đò suối Yến"),
    "🛕 Hà Nội — Chùa Một Cột":
        (21.0359, 105.8337, "chùa đền", "Hà Nội", "Bắc",
         "Chùa hình đóa sen trên cột đá"),
    "🛕 Hà Nội — Chùa Thầy":
        (20.969, 105.545, "chùa đền", "Hà Nội", "Bắc",
         "Chùa cổ trên sườn núi, múa rối nước"),
    "🛕 Hà Nội — Chùa Tây Phương":
        (20.98, 105.55, "chùa đền", "Hà Nội", "Bắc",
         "Chùa ba tầng mái, 18 vị La Hán độc đáo"),
    "🛍️ Hà Nội — Chợ đêm Đồng Xuân":
        (21.0411, 105.8476, "chợ", "Hà Nội", "Bắc",
         "Chợ đêm cuối tuần, ẩm thực phố cổ"),
    "🏛️ Hà Nội — Hoàng thành Thăng Long":
        (21.035, 105.84, "di tích", "Hà Nội", "Bắc",
         "Di sản UNESCO, cấm thành ngàn năm"),
    "🏞️ Hà Nội — Hồ Gươm (Hoàn Kiếm)":
        (21.0287, 105.8524, "danh thắng", "Hà Nội", "Bắc",
         "Hồ trung tâm, tháp Rùa, đền Ngọc Sơn"),
    "💧 Hà Nội — Hồ Tây":
        (21.058, 105.82, "hồ", "Hà Nội", "Bắc",
         "Hồ lớn nhất Hà Nội, chùa Trấn Quốc, phủ Tây Hồ"),
    "🏛️ Hà Nội — Làng cổ Đường Lâm":
        (21.135, 105.475, "di tích", "Hà Nội", "Bắc",
         "Làng Việt cổ đá ong, Sơn Tây"),
    "🧵 Hà Nội — Làng gốm Bát Tràng":
        (20.9933, 105.9006, "làng nghề", "Hà Nội", "Bắc",
         "Làng gốm cổ 700 năm, chợ gốm, trải nghiệm"),
    "🏛️ Hà Nội — Lăng Chủ tịch Hồ Chí Minh":
        (21.0367, 105.8347, "di tích", "Hà Nội", "Bắc",
         "Nơi an nghỉ Bác Hồ, quảng trường Ba Đình"),
    "🏛️ Hà Nội — Nhà tù Hỏa Lò (Hanoi Hilton)":
        (21.0278, 105.8457, "di tích", "Hà Nội", "Bắc",
         "Nhà tù thực dân Pháp, di tích lịch sử"),
    "🌃 Hà Nội — Phố cổ Hà Nội (36 phố phường)":
        (21.034, 105.85, "phố đêm", "Hà Nội", "Bắc",
         "Khu phố cổ, ẩm thực, chợ đêm"),
    "🍜 Hà Nội — Phố ẩm thực Tạ Hiện":
        (21.0345, 105.8515, "ăn uống", "Hà Nội", "Bắc",
         "Phố bia hơi, ngã tư quốc tế phố cổ"),
    "🍜 Hà Nội — Phở Thìn Đặng Dung":
        (21.0362, 105.852, "ăn uống", "Hà Nội", "Bắc",
         "Phở bò xào tỏi trứ danh, hàng dài từ 6am"),
    "🏛️ Hà Nội — Thành Cổ Loa":
        (21.122, 105.877, "di tích", "Hà Nội", "Bắc",
         "Kinh đô An Dương Vương, thành ốc"),
    "🌿 Hà Nội — VQG Ba Vì":
        (21.07, 105.36, "thiên nhiên", "Hà Nội", "Bắc",
         "Núi rừng, đền Thượng, di tích Pháp"),
    "🏛️ Hà Nội — Văn Miếu - Quốc Tử Giám":
        (21.0293, 105.8355, "di tích", "Hà Nội", "Bắc",
         "Trường đại học đầu tiên, bia tiến sĩ"),
    "🏛️ Hưng Yên — Phố Hiến":
        (20.64, 106.06, "di tích", "Hưng Yên", "Bắc",
         "Thương cảng cổ, chùa Chuông, nhãn lồng"),
    "🏛️ Hải Dương — Côn Sơn - Kiếp Bạc":
        (21.11, 106.39, "di tích", "Hải Dương", "Bắc",
         "Đền thờ Trần Hưng Đạo, Nguyễn Trãi"),
    "🏖️ Hải Phòng — Biển Đồ Sơn":
        (20.71, 106.78, "biển", "Hải Phòng", "Bắc",
         "Bãi biển lâu đời, casino, đền Bà Đế"),
    "🏝️ Hải Phòng — Đảo Cát Bà":
        (20.728, 107.048, "đảo", "Hải Phòng", "Bắc",
         "Đảo lớn nhất vịnh, VQG, vịnh Lan Hạ"),
    "🏖️ Nam Định — Biển Thịnh Long":
        (20.02, 106.2, "biển", "Nam Định", "Bắc",
         "Bãi biển Hải Hậu"),
    "🛕 Nam Định — Phủ Dầy":
        (20.28, 106.14, "chùa đền", "Nam Định", "Bắc",
         "Trung tâm tín ngưỡng thờ Mẫu Liễu Hạnh"),
    "🏛️ Nam Định — Đền Trần Nam Định":
        (20.45, 106.18, "di tích", "Nam Định", "Bắc",
         "Đền thờ nhà Trần, lễ khai ấn"),
    "🛕 Ninh Bình — Chùa Bái Đính":
        (20.268, 105.863, "chùa đền", "Ninh Bình", "Bắc",
         "Quần thể chùa lớn nhất Đông Nam Á"),
    "🍜 Ninh Bình — Cơm cháy - Dê núi Ninh Bình":
        (20.2506, 105.9745, "ăn uống", "Ninh Bình", "Bắc",
         "Cơm cháy sốt sườn, dê núi nướng lá lốt"),
    "🏛️ Ninh Bình — Cố đô Hoa Lư":
        (20.287, 105.908, "di tích", "Ninh Bình", "Bắc",
         "Kinh đô đầu tiên, đền vua Đinh vua Lê"),
    "🏞️ Ninh Bình — Hang Múa":
        (20.23, 105.94, "danh thắng", "Ninh Bình", "Bắc",
         "Leo 500 bậc ngắm toàn cảnh Tam Cốc"),
    "🏞️ Ninh Bình — Quần thể Tràng An":
        (20.25, 105.92, "danh thắng", "Ninh Bình", "Bắc",
         "Di sản hỗn hợp UNESCO, hang xuyên núi, đi thuyền"),
    "🏞️ Ninh Bình — Tam Cốc - Bích Động":
        (20.22, 105.935, "danh thắng", "Ninh Bình", "Bắc",
         "Hạ Long trên cạn, Nam thiên đệ nhị động"),
    "🌿 Ninh Bình — Vân Long":
        (20.33, 105.88, "thiên nhiên", "Ninh Bình", "Bắc",
         "Khu bảo tồn đất ngập nước, voọc mông trắng"),
    "🌿 Phú Thọ — VQG Xuân Sơn":
        (21.13, 104.95, "thiên nhiên", "Phú Thọ", "Bắc",
         "Rừng nguyên sinh, hang động, bản Dao Mường"),
    "🏛️ Phú Thọ — Đền Hùng":
        (21.366, 105.323, "di tích", "Phú Thọ", "Bắc",
         "Đất tổ Hùng Vương, giỗ tổ mùng 10/3"),
    "🛕 Thái Bình — Chùa Keo Thái Bình":
        (20.54, 106.4, "chùa đền", "Thái Bình", "Bắc",
         "Chùa cổ gác chuông gỗ độc đáo"),
    "🏖️ Thái Bình — Khu du lịch Cồn Vành":
        (20.4, 106.55, "biển", "Thái Bình", "Bắc",
         "Cồn biển sinh thái, rừng ngập mặn"),
    "💧 Vĩnh Phúc — Hồ Đại Lải":
        (21.31, 105.74, "hồ", "Vĩnh Phúc", "Bắc",
         "Hồ resort, golf, nghỉ dưỡng cuối tuần HN"),
    "🛕 Vĩnh Phúc — Thiền viện Trúc Lâm Tây Thiên":
        (21.44, 105.59, "chùa đền", "Vĩnh Phúc", "Bắc",
         "Thiền viện lớn, khu danh thắng Tây Thiên"),
    "🏞️ Vĩnh Phúc — Thị trấn Tam Đảo":
        (21.456, 105.643, "danh thắng", "Vĩnh Phúc", "Bắc",
         "Thị trấn nghỉ mát trên núi, mây mù, nhà thờ đá"),

    # ── Đông Bắc (32 điểm) ──
    "🛕 Bắc Giang — Chùa Vĩnh Nghiêm Bắc Giang":
        (21.24, 106.35, "chùa đền", "Bắc Giang", "Đông Bắc",
         "Chốn tổ Thiền phái Trúc Lâm, mộc bản UNESCO"),
    "🛕 Bắc Giang — Tây Yên Tử":
        (21.2, 106.73, "chùa đền", "Bắc Giang", "Đông Bắc",
         "Sườn tây Yên Tử, cáp treo"),
    "🧵 Bắc Giang — Vải thiều Lục Ngạn":
        (21.38, 106.55, "làng nghề", "Bắc Giang", "Đông Bắc",
         "Vùng vải thiều lớn nhất VN, tháng 5-6"),
    "💧 Bắc Kạn — Hồ Ba Bể":
        (22.4, 105.62, "hồ", "Bắc Kạn", "Đông Bắc",
         "Hồ nước ngọt tự nhiên lớn nhất VN, ~500ha, khu Ramsar"),
    "💦 Bắc Kạn — Thác Đầu Đẳng":
        (22.45, 105.6, "thác", "Bắc Kạn", "Đông Bắc",
         "Thác ba tầng trên sông Năng"),
    "🕳️ Bắc Kạn — Động Puông":
        (22.43, 105.63, "hang động", "Bắc Kạn", "Đông Bắc",
         "Hang sông xuyên núi, dơi, đi thuyền"),
    "💧 Cao Bằng — Hồ Thang Hen":
        (22.78, 106.36, "hồ", "Cao Bằng", "Đông Bắc",
         "Hồ trên núi giữa cao nguyên đá"),
    "🏛️ Cao Bằng — Khu di tích Pác Bó":
        (22.98, 106.17, "di tích", "Cao Bằng", "Đông Bắc",
         "Hang Cốc Bó, suối Lê Nin, nơi Bác Hồ về nước"),
    "💦 Cao Bằng — Thác Bản Giốc":
        (22.853, 106.723, "thác", "Cao Bằng", "Đông Bắc",
         "Thác biên giới, rộng ~300m cao ~35m 3 tầng, sông Quây Sơn"),
    "🕳️ Cao Bằng — Động Ngườm Ngao":
        (22.845, 106.71, "hang động", "Cao Bằng", "Đông Bắc",
         "Động thạch nhũ dài gần thác Bản Giốc"),
    "🏛️ Hà Giang — Cột cờ Lũng Cú":
        (23.362, 105.314, "di tích", "Hà Giang", "Đông Bắc",
         "Điểm cực Bắc Tổ quốc, độ cao 1470m, đỉnh núi Rồng"),
    "🏛️ Hà Giang — Dinh thự họ Vương":
        (23.17, 105.28, "di tích", "Hà Giang", "Đông Bắc",
         "Dinh Vua Mèo, kiến trúc Mông-Hoa"),
    "🏞️ Hà Giang — Núi đôi Quản Bạ":
        (23.07, 104.99, "danh thắng", "Hà Giang", "Đông Bắc",
         "Núi đôi Cô Tiên, cổng trời Quản Bạ"),
    "🏞️ Hà Giang — Ruộng bậc thang Hoàng Su Phì":
        (22.75, 104.68, "danh thắng", "Hà Giang", "Đông Bắc",
         "Ruộng bậc thang di sản, mùa nước đổ"),
    "🌿 Hà Giang — Sông Nho Quế / hẻm Tu Sản":
        (23.22, 105.36, "thiên nhiên", "Hà Giang", "Đông Bắc",
         "Hẻm vực sâu nhất Đông Nam Á, thuyền kayak"),
    "🏞️ Hà Giang — Đèo Mã Pí Lèng":
        (23.247, 105.345, "danh thắng", "Hà Giang", "Đông Bắc",
         "Tứ đại đỉnh đèo, hẻm sông Nho Quế"),
    "🏞️ Hà Giang — Đồng Văn (phố cổ)":
        (23.278, 105.362, "danh thắng", "Hà Giang", "Đông Bắc",
         "Phố cổ cao nguyên đá, chợ phiên"),
    "🏞️ Lạng Sơn — Cửa khẩu Hữu Nghị":
        (21.96, 106.7, "danh thắng", "Lạng Sơn", "Đông Bắc",
         "Cửa khẩu quốc tế Việt-Trung"),
    "⛰️ Lạng Sơn — Đỉnh Mẫu Sơn":
        (21.85, 106.92, "núi", "Lạng Sơn", "Đông Bắc",
         "Vùng núi mát lạnh có tuyết, chè, đào"),
    "🕳️ Lạng Sơn — Động Tam Thanh":
        (21.856, 106.755, "hang động", "Lạng Sơn", "Đông Bắc",
         "Động chùa trong lòng núi, phố cổ Kỳ Lừa"),
    "🏖️ Quảng Ninh — Biển Trà Cổ Móng Cái":
        (21.48, 108.03, "biển", "Quảng Ninh", "Đông Bắc",
         "Bãi biển dài, nhà thờ Trà Cổ, gần biên giới"),
    "🕳️ Quảng Ninh — Hang Sửng Sốt":
        (20.8456, 107.0897, "hang động", "Quảng Ninh", "Đông Bắc",
         "Hang động đẹp nhất Hạ Long, 3 ngăn rộng"),
    "⛰️ Quảng Ninh — Núi Bài Thơ":
        (20.953, 107.08, "núi", "Quảng Ninh", "Đông Bắc",
         "Núi giữa TP Hạ Long, thơ khắc đá cổ"),
    "🏝️ Quảng Ninh — VQG Bái Tử Long":
        (21.1, 107.6, "đảo", "Quảng Ninh", "Đông Bắc",
         "Vịnh hoang sơ ít khách hơn Hạ Long"),
    "🏞️ Quảng Ninh — Vịnh Hạ Long":
        (20.91, 107.183, "danh thắng", "Quảng Ninh", "Đông Bắc",
         "Di sản UNESCO, hàng nghìn đảo đá vôi"),
    "🛕 Quảng Ninh — Yên Tử":
        (21.16, 106.72, "chùa đền", "Quảng Ninh", "Đông Bắc",
         "Đất tổ Thiền Trúc Lâm, chùa Đồng, cáp treo"),
    "🏝️ Quảng Ninh — Đảo Cô Tô":
        (20.98, 107.77, "đảo", "Quảng Ninh", "Đông Bắc",
         "Đảo nước trong, bãi Hồng Vàn, hải đăng"),
    "🏝️ Quảng Ninh — Đảo Vân Đồn":
        (20.96, 107.51, "đảo", "Quảng Ninh", "Đông Bắc",
         "Đặc khu kinh tế, cảng cổ, hải sản"),
    "🏛️ Thái Nguyên — ATK Định Hóa":
        (21.87, 105.6, "di tích", "Thái Nguyên", "Đông Bắc",
         "An toàn khu kháng chiến, rừng cọ"),
    "💧 Thái Nguyên — Hồ Núi Cốc":
        (21.55, 105.72, "hồ", "Thái Nguyên", "Đông Bắc",
         "Hồ nhân tạo, huyền thoại nàng Công chàng Cốc"),
    "🧵 Thái Nguyên — Đồi chè Tân Cương":
        (21.54, 105.76, "làng nghề", "Thái Nguyên", "Đông Bắc",
         "Vùng chè nổi tiếng nhất Việt Nam"),
    "💧 Tuyên Quang — Khu du lịch Na Hang":
        (22.49, 105.39, "hồ", "Tuyên Quang", "Đông Bắc",
         "Hồ sinh thái, thác Khuổi Nhi, rừng nguyên sinh"),

    # ── Tây Bắc (24 điểm) ──
    "💧 Hòa Bình — Hồ Hòa Bình":
        (20.82, 105.33, "hồ", "Hòa Bình", "Tây Bắc",
         "Hồ thủy điện, du thuyền, đảo, đền Thác Bờ"),
    "🏘️ Hòa Bình — Mai Châu - Bản Lác":
        (20.66, 105.05, "làng bản dân tộc", "Hòa Bình", "Tây Bắc",
         "Bản Thái, nhà sàn, homestay, ruộng lúa"),
    "🕳️ Lai Châu — Pu Sam Cáp":
        (22.39, 103.42, "hang động", "Lai Châu", "Tây Bắc",
         "Hệ hang động trên núi gần thành phố"),
    "🏞️ Lai Châu — Sìn Hồ":
        (22.36, 103.24, "danh thắng", "Lai Châu", "Tây Bắc",
         "Cao nguyên mát mẻ, chợ phiên, suối nước nóng"),
    "🏞️ Lai Châu — Đèo Ô Quy Hồ":
        (22.345, 103.77, "danh thắng", "Lai Châu", "Tây Bắc",
         "Tứ đại đỉnh đèo, ranh giới Lào Cai-Lai Châu"),
    "🏘️ Lào Cai — Bản Cát Cát":
        (22.33, 103.832, "làng bản dân tộc", "Lào Cai", "Tây Bắc",
         "Bản người Mông, thác, guồng nước"),
    "🏘️ Lào Cai — Bản Tả Phìn":
        (22.38, 103.87, "làng bản dân tộc", "Lào Cai", "Tây Bắc",
         "Bản Dao đỏ, tắm lá thuốc, thêu"),
    "🛍️ Lào Cai — Chợ phiên Bắc Hà":
        (22.537, 104.29, "chợ", "Lào Cai", "Tây Bắc",
         "Chợ phiên Chủ nhật dân tộc, ngựa, thổ cẩm"),
    "🏞️ Lào Cai — Sa Pa (trung tâm)":
        (22.336, 103.844, "danh thắng", "Lào Cai", "Tây Bắc",
         "Thị trấn mù sương, nhà thờ đá, chợ vùng cao"),
    "🌿 Lào Cai — Thung lũng Mường Hoa":
        (22.31, 103.88, "thiên nhiên", "Lào Cai", "Tây Bắc",
         "Ruộng bậc thang, bãi đá cổ khắc"),
    "🌿 Lào Cai — Y Tý":
        (22.65, 103.8, "thiên nhiên", "Lào Cai", "Tây Bắc",
         "Biển mây, rừng nguyên sinh, bản Hà Nhì"),
    "⛰️ Lào Cai — Đỉnh Fansipan":
        (22.303, 103.775, "núi", "Lào Cai", "Tây Bắc",
         "Nóc nhà Đông Dương 3143m, cáp treo"),
    "🌿 Sơn La — Cao nguyên Mộc Châu":
        (20.83, 104.68, "thiên nhiên", "Sơn La", "Tây Bắc",
         "Đồi chè, vườn mận, hoa cải, đồng cỏ"),
    "🏛️ Sơn La — Nhà tù Sơn La":
        (21.327, 103.913, "di tích", "Sơn La", "Tây Bắc",
         "Di tích nhà tù thực dân, cây đào Tô Hiệu"),
    "💦 Sơn La — Thác Dải Yếm":
        (20.825, 104.61, "thác", "Sơn La", "Tây Bắc",
         "Thác Nàng, cầu kính, Mộc Châu"),
    "🏞️ Sơn La — Đèo Pha Đin":
        (21.56, 103.55, "danh thắng", "Sơn La", "Tây Bắc",
         "Tứ đại đỉnh đèo, view núi rừng"),
    "🌿 Yên Bái — Cánh đồng Mường Lò (Nghĩa Lộ)":
        (21.598, 104.5, "thiên nhiên", "Yên Bái", "Tây Bắc",
         "Cánh đồng lớn, văn hóa Thái, xòe"),
    "💧 Yên Bái — Hồ Thác Bà":
        (21.9, 105.05, "hồ", "Yên Bái", "Tây Bắc",
         "Hồ thủy điện đầu tiên VN, 1331 đảo nhỏ"),
    "🏞️ Yên Bái — Ruộng bậc thang Mù Cang Chải":
        (21.85, 104.09, "danh thắng", "Yên Bái", "Tây Bắc",
         "Ruộng bậc thang di tích quốc gia, mùa lúa chín"),
    "🏞️ Điện Biên — A Pa Chải":
        (22.4, 102.14, "danh thắng", "Điện Biên", "Tây Bắc",
         "Cực Tây Tổ quốc, ngã ba biên giới Việt-Trung-Lào"),
    "🏛️ Điện Biên — Di tích Điện Biên Phủ (đồi A1)":
        (21.386, 103.023, "di tích", "Điện Biên", "Tây Bắc",
         "Cứ điểm A1 lịch sử chiến dịch 1954"),
    "🏛️ Điện Biên — Hầm De Castries":
        (21.384, 103.018, "di tích", "Điện Biên", "Tây Bắc",
         "Hầm chỉ huy tướng Pháp bị bắt sống"),
    "💧 Điện Biên — Hồ Pá Khoang":
        (21.46, 103.12, "hồ", "Điện Biên", "Tây Bắc",
         "Hồ sinh thái gần Mường Phăng"),
    "🏛️ Điện Biên — Mường Phăng":
        (21.47, 103.13, "di tích", "Điện Biên", "Tây Bắc",
         "Sở chỉ huy chiến dịch của Đại tướng Võ Nguyên Giáp"),

}

# name -> (lat, lon) — kept because most callers only ever want the coordinate.
VN_PLACES: Dict[str, Coord] = {k: (v[0], v[1]) for k, v in VN_PLACE_INFO.items()}

REGIONS: List[str] = ["Nam", "Tây Nguyên", "Trung", "Bắc", "Đông Bắc", "Tây Bắc"]
ALL_REGIONS = "— Tất cả vùng —"


def places_in(region: str) -> List[str]:
    """Place names in one region, or every name for ALL_REGIONS."""
    if region == ALL_REGIONS:
        return list(VN_PLACE_INFO.keys())
    return [k for k, v in VN_PLACE_INFO.items() if v[4] == region]


def note_of(name: str) -> str:
    info = VN_PLACE_INFO.get(name)
    return info[5] if info else ""


VN_CENTER: Coord = (16.0, 107.5)  # roughly the middle of Vietnam


def geocode(query: str, limit: int = 6, timeout: float = 10.0) -> List[Tuple[float, float, str]]:
    """Resolve free text to a list of (lat, lon, display_name). [] on failure."""
    query = (query or "").strip()
    if not query:
        return []
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": limit, "countrycodes": "vn"},
            headers={"User-Agent": "BumpSpoof/2.0 (personal travel spoofer)"},
            timeout=timeout,
        )
        return [
            (float(item["lat"]), float(item["lon"]), item.get("display_name", query))
            for item in r.json()
        ]
    except Exception:
        return []
