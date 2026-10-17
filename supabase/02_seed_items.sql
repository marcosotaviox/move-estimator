-- AI Move Estimator: standard item volumes (starting values, calibrate with real jobs)
-- volume_m3 = assembled / as moved. dismantled_volume_m3 only for items that come apart.

insert into item_catalog
  (name, category, aliases, volume_m3, dismantlable, dismantled_volume_m3, heavy)
values
-- Living room
('3 seater sofa',          'living',  '{"3 seater lounge","three seater couch"}', 1.50, false, null, false),
('2 seater sofa',          'living',  '{"2 seater lounge","loveseat"}',          1.00, false, null, false),
('Corner sofa / modular',  'living',  '{"l-shape sofa","sectional","modular lounge"}', 2.50, true, 2.20, false),
('Armchair',               'living',  '{"recliner","accent chair"}',             0.60, false, null, false),
('Coffee table',           'living',  '{}',                                      0.30, false, null, false),
('Side table',             'living',  '{"lamp table","end table"}',              0.15, false, null, false),
('TV unit',                'living',  '{"entertainment unit","tv cabinet"}',     0.60, false, null, false),
('TV up to 55 inch',       'living',  '{"television"}',                          0.25, false, null, false),
('TV over 55 inch',        'living',  '{"large tv"}',                            0.40, false, null, false),
('Bookcase',               'living',  '{"bookshelf","shelving unit"}',           0.60, true, 0.30, false),
('Floor lamp',             'living',  '{"standing lamp"}',                       0.15, false, null, false),
('Rug',                    'living',  '{"carpet"}',                              0.10, false, null, false),
('Piano upright',          'living',  '{"upright piano"}',                       1.50, false, null, true),

-- Dining
('Dining table 4 seater',  'dining',  '{}',                                      0.70, true, 0.40, false),
('Dining table 6 seater',  'dining',  '{}',                                      1.00, true, 0.50, false),
('Dining table 8 seater',  'dining',  '{}',                                      1.40, true, 0.70, false),
('Dining chair',           'dining',  '{"chair"}',                               0.20, false, null, false),
('Buffet / sideboard',     'dining',  '{"credenza","hutch"}',                    0.90, false, null, false),
('Bar stool',              'dining',  '{"stool"}',                               0.15, false, null, false),

-- Bedroom
('King bed',               'bedroom', '{"king bed base","king ensemble"}',       2.00, true, 1.30, false),
('Queen bed',              'bedroom', '{"queen bed base","queen ensemble"}',     1.60, true, 1.10, false),
('Double bed',             'bedroom', '{"double ensemble"}',                     1.30, true, 0.90, false),
('Single bed',             'bedroom', '{"single ensemble"}',                     0.90, true, 0.60, false),
('Bunk bed',               'bedroom', '{}',                                      1.50, true, 0.80, false),
('Cot',                    'bedroom', '{"crib","baby cot"}',                     0.50, true, 0.25, false),
('Bedside table',          'bedroom', '{"nightstand"}',                          0.20, false, null, false),
('Chest of drawers',       'bedroom', '{"tallboy","dresser"}',                   0.60, false, null, false),
('Dressing table',         'bedroom', '{"vanity"}',                              0.60, false, null, false),
('Wardrobe single',        'bedroom', '{"single wardrobe","robe"}',              0.90, true, 0.50, false),
('Wardrobe double',        'bedroom', '{"double wardrobe"}',                     1.60, true, 0.90, false),

-- Kitchen and laundry
('Fridge single door',     'kitchen', '{"small fridge","bar fridge"}',           0.60, false, null, true),
('Fridge double door',     'kitchen', '{"fridge freezer","top mount fridge"}',   1.00, false, null, true),
('Fridge side by side',    'kitchen', '{"french door fridge","american fridge"}',1.50, false, null, true),
('Chest freezer',          'kitchen', '{"freezer"}',                             0.80, false, null, true),
('Microwave',              'kitchen', '{}',                                      0.10, false, null, false),
('Dishwasher',             'kitchen', '{}',                                      0.50, false, null, true),
('Washing machine',        'laundry', '{"washer"}',                              0.60, false, null, true),
('Dryer',                  'laundry', '{"clothes dryer"}',                       0.50, false, null, false),

-- Office
('Desk',                   'office',  '{"study desk","computer desk"}',          0.80, true, 0.40, false),
('Office chair',           'office',  '{"desk chair"}',                          0.30, false, null, false),
('Filing cabinet 2 drawer','office',  '{}',                                      0.30, false, null, false),
('Filing cabinet 4 drawer','office',  '{}',                                      0.60, false, null, true),
('Computer monitor',       'office',  '{"screen"}',                              0.08, false, null, false),

-- Outdoor and garage
('BBQ',                    'outdoor', '{"barbecue"}',                            0.60, false, null, false),
('Outdoor setting',        'outdoor', '{"outdoor table and chairs"}',            1.20, true, 0.80, false),
('Sun lounger',            'outdoor', '{"day bed outdoor"}',                     0.40, false, null, false),
('Lawn mower',             'outdoor', '{"mower"}',                               0.40, false, null, false),
('Bicycle',                'outdoor', '{"bike"}',                                0.40, false, null, false),
('Pot plant large',        'outdoor', '{"planter"}',                             0.20, false, null, false),
('Tool box',               'garage',  '{"toolbox"}',                             0.10, false, null, false),
('Garage shelving',        'garage',  '{"metal shelving"}',                      0.50, true, 0.20, false),
('Gym bench',              'garage',  '{"weight bench"}',                        0.40, false, null, false),
('Treadmill',              'garage',  '{}',                                      0.90, false, null, true),
('Safe',                   'garage',  '{}',                                      0.30, false, null, true),

-- Boxes and misc
('Standard box',           'boxes',   '{"carton","packing box"}',                0.10, false, null, false),
('Book box',               'boxes',   '{"small box"}',                           0.06, false, null, false),
('Wardrobe box',           'boxes',   '{"porta robe","hanging box"}',            0.30, false, null, false),
('Suitcase',               'boxes',   '{"luggage"}',                             0.10, false, null, false),
('Mattress queen',         'bedroom', '{"queen mattress"}',                      0.60, false, null, false),
('Mirror large',           'misc',    '{"wall mirror"}',                         0.10, false, null, false),
('Painting / artwork',     'misc',    '{"frame","picture"}',                     0.05, false, null, false);
