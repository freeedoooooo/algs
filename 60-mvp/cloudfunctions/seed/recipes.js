// cloudfunctions/seed/recipes.js
// 预置菜谱库（种子数据）
// 字段说明：
//   type: meat(荤) | vegetable(素) | soup(汤)
//   tags: 场景标签 quick(快手) | easy(简单) | feast(周末大菜)
//   season: 时令月份数组，[] 表示全年供应
//   estimatedTime: 预计总时长(分钟)
//   timelineSteps[].type: prep(备菜) | cook(烹饪) | wait(等待)
//   timelineSteps[].timer: 该节点倒计时分钟数(可选)

const recipes = [
  // ================= 荤菜 =================
  {
    _id: 'recipe_tomato_egg',
    name: '番茄炒蛋',
    type: 'meat',
    tags: ['quick', 'easy'],
    season: [],
    estimatedTime: 12,
    servings: 2,
    ingredientsNeeded: [
      { name: '番茄', qty: 2, unit: '个' },
      { name: '鸡蛋', qty: 3, unit: '个' }
    ],
    checklist: {
      mainIngredients: ['番茄 2个', '鸡蛋 3个', '小葱 1根'],
      seasonings: ['盐', '糖', '食用油'],
      tools: ['炒锅', '锅铲', '碗']
    },
    timelineSteps: [
      { time: '00:00', action: '番茄切块，鸡蛋加少许盐打散，葱切花', type: 'prep' },
      { time: '03:00', action: '热锅凉油，倒入蛋液炒至凝固盛出', type: 'cook', timer: 2 },
      { time: '06:00', action: '原锅下番茄翻炒出汁，加半勺糖、适量盐', type: 'cook', timer: 3 },
      { time: '10:00', action: '倒回鸡蛋翻炒均匀，撒葱花出锅', type: 'cook' }
    ],
    tip: '蛋液炒到刚凝固就盛出，回锅时才嫩。'
  },
  {
    _id: 'recipe_cola_wings',
    name: '可乐鸡翅',
    type: 'meat',
    tags: ['easy', 'feast'],
    season: [],
    estimatedTime: 30,
    servings: 2,
    ingredientsNeeded: [
      { name: '鸡翅中', qty: 8, unit: '个' },
      { name: '可乐', qty: 330, unit: 'ml' }
    ],
    checklist: {
      mainIngredients: ['鸡翅中 8个', '可乐 1罐', '姜 3片'],
      seasonings: ['生抽', '老抽', '料酒', '食用油'],
      tools: ['炒锅', '锅铲']
    },
    timelineSteps: [
      { time: '00:00', action: '鸡翅两面划刀，冷水下锅加料酒焯水', type: 'prep' },
      { time: '05:00', action: '捞出沥干，热锅少油煎至两面金黄', type: 'cook', timer: 5 },
      { time: '11:00', action: '倒入可乐没过鸡翅，加生抽1勺、老抽半勺、姜片', type: 'cook' },
      { time: '13:00', action: '大火烧开转中小火炖煮收汁', type: 'wait', timer: 15 },
      { time: '28:00', action: '汤汁浓稠裹满鸡翅即可出锅', type: 'cook' }
    ],
    tip: '可乐含糖，收汁时要不停翻动防止糊锅。'
  },
  {
    _id: 'recipe_pepper_pork',
    name: '青椒肉丝',
    type: 'meat',
    tags: ['quick', 'easy'],
    season: [],
    estimatedTime: 15,
    servings: 2,
    ingredientsNeeded: [
      { name: '猪里脊', qty: 200, unit: 'g' },
      { name: '青椒', qty: 2, unit: '个' }
    ],
    checklist: {
      mainIngredients: ['猪里脊 200g', '青椒 2个', '蒜 2瓣'],
      seasonings: ['生抽', '料酒', '淀粉', '盐', '食用油'],
      tools: ['炒锅', '锅铲', '刀']
    },
    timelineSteps: [
      { time: '00:00', action: '里脊切丝，用料酒+生抽+淀粉抓匀腌10分钟；青椒切丝', type: 'prep' },
      { time: '10:00', action: '热锅凉油下肉丝滑炒至变色盛出', type: 'cook', timer: 2 },
      { time: '12:00', action: '下蒜末青椒丝翻炒断生，回锅肉丝调味', type: 'cook', timer: 2 },
      { time: '15:00', action: '加盐炒匀出锅', type: 'cook' }
    ],
    tip: '肉丝腌制时加点油，下锅不粘连更嫩滑。'
  },
  {
    _id: 'recipe_braised_pork',
    name: '红烧肉',
    type: 'meat',
    tags: ['feast'],
    season: [],
    estimatedTime: 75,
    servings: 3,
    ingredientsNeeded: [
      { name: '五花肉', qty: 500, unit: 'g' }
    ],
    checklist: {
      mainIngredients: ['五花肉 500g', '姜 4片', '葱 2根', '八角 2个'],
      seasonings: ['冰糖', '生抽', '老抽', '料酒', '盐'],
      tools: ['炒锅', '锅铲', '砂锅(可选)']
    },
    timelineSteps: [
      { time: '00:00', action: '五花肉切块，冷水下锅加料酒焯水去血沫', type: 'prep' },
      { time: '08:00', action: '锅中少油下冰糖小火炒出糖色', type: 'cook', timer: 4 },
      { time: '13:00', action: '下肉块翻炒上色，加葱姜八角、生抽老抽', type: 'cook', timer: 3 },
      { time: '17:00', action: '加热水没过肉，大火烧开转小火慢炖', type: 'wait', timer: 45 },
      { time: '62:00', action: '开盖加盐，大火收汁至浓稠油亮', type: 'cook', timer: 8 },
      { time: '72:00', action: '出锅装盘', type: 'cook' }
    ],
    tip: '一定要加热水，冷水会让肉质收缩变柴。'
  },
  {
    _id: 'recipe_kungpao_chicken',
    name: '宫保鸡丁',
    type: 'meat',
    tags: ['easy', 'feast'],
    season: [],
    estimatedTime: 25,
    servings: 2,
    ingredientsNeeded: [
      { name: '鸡胸肉', qty: 300, unit: 'g' },
      { name: '花生米', qty: 50, unit: 'g' }
    ],
    checklist: {
      mainIngredients: ['鸡胸肉 300g', '油炸花生米 50g', '干辣椒 5个', '葱 1根', '蒜 3瓣'],
      seasonings: ['生抽', '醋', '糖', '淀粉', '料酒', '豆瓣酱'],
      tools: ['炒锅', '锅铲', '碗']
    },
    timelineSteps: [
      { time: '00:00', action: '鸡丁加料酒+淀粉+生抽腌15分钟；调碗汁(生抽2醋2糖2淀粉1水)', type: 'prep' },
      { time: '15:00', action: '热油下干辣椒蒜片爆香，下鸡丁炒至变白', type: 'cook', timer: 3 },
      { time: '19:00', action: '倒入碗汁快速翻炒裹匀', type: 'cook', timer: 2 },
      { time: '22:00', action: '关火倒入花生米和葱段拌匀出锅', type: 'cook' }
    ],
    tip: '花生米最后放，才能保持酥脆。'
  },
  {
    _id: 'recipe_sweet_sour_pork',
    name: '糖醋里脊',
    type: 'meat',
    tags: ['feast'],
    season: [],
    estimatedTime: 40,
    servings: 2,
    ingredientsNeeded: [
      { name: '猪里脊', qty: 300, unit: 'g' }
    ],
    checklist: {
      mainIngredients: ['猪里脊 300g', '鸡蛋 1个', '淀粉 适量', '白芝麻 少许'],
      seasonings: ['番茄酱', '白醋', '糖', '生抽', '盐', '食用油'],
      tools: ['炒锅', '炸锅/深锅', '漏勺']
    },
    timelineSteps: [
      { time: '00:00', action: '里脊切条加盐料酒腌10分钟，裹蛋液和淀粉', type: 'prep' },
      { time: '12:00', action: '油温六成热下锅炸至定型金黄捞出', type: 'cook', timer: 6 },
      { time: '20:00', action: '油温升高复炸30秒至酥脆捞出', type: 'cook', timer: 1 },
      { time: '24:00', action: '锅留底油，下番茄酱+糖+醋+生抽熬汁', type: 'cook', timer: 3 },
      { time: '30:00', action: '倒入里脊快速翻裹，撒芝麻出锅', type: 'cook' }
    ],
    tip: '复炸是酥脆的关键，糖醋汁要现调现熬。'
  },

  // ================= 素菜 =================
  {
    _id: 'recipe_garlic_broccoli',
    name: '蒜蓉西兰花',
    type: 'vegetable',
    tags: ['quick', 'easy'],
    season: [9, 10, 11, 12, 1, 2, 3],
    estimatedTime: 10,
    servings: 2,
    ingredientsNeeded: [
      { name: '西兰花', qty: 1, unit: '颗' },
      { name: '蒜', qty: 4, unit: '瓣' }
    ],
    checklist: {
      mainIngredients: ['西兰花 1颗', '蒜 4瓣'],
      seasonings: ['盐', '食用油', '蚝油(可选)'],
      tools: ['炒锅', '锅铲', '汤锅(焯水)']
    },
    timelineSteps: [
      { time: '00:00', action: '西兰花掰小朵盐水浸泡，蒜切末', type: 'prep' },
      { time: '03:00', action: '水开下西兰花焯1分钟捞出过凉', type: 'cook', timer: 1 },
      { time: '05:00', action: '热油下蒜末爆香，下西兰花翻炒', type: 'cook', timer: 2 },
      { time: '08:00', action: '加盐和少许蚝油炒匀出锅', type: 'cook' }
    ],
    tip: '焯水后过凉能保持翠绿爽脆。'
  },
  {
    _id: 'recipe_hand_torn_cabbage',
    name: '手撕包菜',
    type: 'vegetable',
    tags: ['quick', 'easy'],
    season: [],
    estimatedTime: 12,
    servings: 2,
    ingredientsNeeded: [
      { name: '圆白菜', qty: 0.5, unit: '颗' },
      { name: '干辣椒', qty: 3, unit: '个' }
    ],
    checklist: {
      mainIngredients: ['圆白菜 半颗', '干辣椒 3个', '蒜 3瓣'],
      seasonings: ['生抽', '醋', '盐', '食用油'],
      tools: ['炒锅', '锅铲']
    },
    timelineSteps: [
      { time: '00:00', action: '包菜手撕成片洗净沥干，蒜切片', type: 'prep' },
      { time: '04:00', action: '热油下蒜片干辣椒爆香', type: 'cook', timer: 1 },
      { time: '06:00', action: '大火下包菜快速翻炒', type: 'cook', timer: 3 },
      { time: '10:00', action: '沿锅边淋生抽和醋，加盐炒匀出锅', type: 'cook' }
    ],
    tip: '全程大火快炒，包菜才脆嫩不出水。'
  },
  {
    _id: 'recipe_cucumber_salad',
    name: '凉拌黄瓜',
    type: 'vegetable',
    tags: ['quick', 'easy'],
    season: [5, 6, 7, 8],
    estimatedTime: 8,
    servings: 2,
    ingredientsNeeded: [
      { name: '黄瓜', qty: 2, unit: '根' },
      { name: '蒜', qty: 3, unit: '瓣' }
    ],
    checklist: {
      mainIngredients: ['黄瓜 2根', '蒜 3瓣'],
      seasonings: ['生抽', '醋', '糖', '香油', '辣椒油(可选)', '盐'],
      tools: ['刀', '碗', '擀面杖(拍黄瓜)']
    },
    timelineSteps: [
      { time: '00:00', action: '黄瓜拍裂切段，加盐腌5分钟杀水', type: 'prep', },
      { time: '05:00', action: '倒掉腌出的水，加蒜末和所有调料', type: 'cook' },
      { time: '07:00', action: '拌匀静置入味即可', type: 'wait', timer: 1 }
    ],
    tip: '拍裂比切片更入味，腌水一定要倒掉。'
  },
  {
    _id: 'recipe_hot_potato',
    name: '酸辣土豆丝',
    type: 'vegetable',
    tags: ['quick', 'easy'],
    season: [],
    estimatedTime: 15,
    servings: 2,
    ingredientsNeeded: [
      { name: '土豆', qty: 2, unit: '个' },
      { name: '干辣椒', qty: 3, unit: '个' }
    ],
    checklist: {
      mainIngredients: ['土豆 2个', '干辣椒 3个', '蒜 2瓣', '青椒 1个(配色)'],
      seasonings: ['白醋', '盐', '花椒(可选)', '食用油'],
      tools: ['炒锅', '锅铲', '刨丝器/刀']
    },
    timelineSteps: [
      { time: '00:00', action: '土豆切细丝，清水冲洗去淀粉后沥干', type: 'prep' },
      { time: '06:00', action: '热油下花椒干辣椒蒜爆香', type: 'cook', timer: 1 },
      { time: '08:00', action: '大火下土豆丝快速翻炒', type: 'cook', timer: 3 },
      { time: '12:00', action: '沿锅边淋白醋，加盐青椒丝炒匀出锅', type: 'cook' }
    ],
    tip: '洗去淀粉是关键，成品才根根分明爽脆。'
  },
  {
    _id: 'recipe_di_san_xian',
    name: '地三鲜',
    type: 'vegetable',
    tags: ['easy'],
    season: [6, 7, 8, 9],
    estimatedTime: 30,
    servings: 2,
    ingredientsNeeded: [
      { name: '茄子', qty: 1, unit: '个' },
      { name: '土豆', qty: 1, unit: '个' },
      { name: '青椒', qty: 1, unit: '个' }
    ],
    checklist: {
      mainIngredients: ['茄子 1个', '土豆 1个', '青椒 1个', '蒜 3瓣'],
      seasonings: ['生抽', '老抽', '糖', '淀粉', '盐', '食用油'],
      tools: ['炒锅', '炸锅/深锅', '漏勺']
    },
    timelineSteps: [
      { time: '00:00', action: '茄子土豆切滚刀块，茄子撒盐腌5分钟挤水；调碗汁', type: 'prep' },
      { time: '08:00', action: '土豆块炸至金黄捞出', type: 'cook', timer: 5 },
      { time: '14:00', action: '茄子下锅炸软捞出，青椒过油', type: 'cook', timer: 4 },
      { time: '20:00', action: '锅留底油下蒜爆香，倒回所有食材', type: 'cook', timer: 2 },
      { time: '24:00', action: '淋入碗汁翻炒裹匀出锅', type: 'cook' }
    ],
    tip: '茄子先腌后挤水，能少吸很多油。'
  },
  {
    _id: 'recipe_stir_fry_greens',
    name: '清炒时蔬',
    type: 'vegetable',
    tags: ['quick', 'easy'],
    season: [],
    estimatedTime: 8,
    servings: 2,
    ingredientsNeeded: [
      { name: '当季绿叶菜', qty: 300, unit: 'g' },
      { name: '蒜', qty: 3, unit: '瓣' }
    ],
    checklist: {
      mainIngredients: ['当季绿叶菜 300g', '蒜 3瓣'],
      seasonings: ['盐', '食用油'],
      tools: ['炒锅', '锅铲']
    },
    timelineSteps: [
      { time: '00:00', action: '青菜洗净沥干，蒜切末', type: 'prep' },
      { time: '03:00', action: '热油下蒜末爆香', type: 'cook', timer: 1 },
      { time: '04:00', action: '大火下青菜快速翻炒至断生', type: 'cook', timer: 2 },
      { time: '07:00', action: '加盐炒匀立即出锅', type: 'cook' }
    ],
    tip: '青菜一定要沥干，下锅才不出水。'
  },

  // ================= 汤 =================
  {
    _id: 'recipe_seaweed_egg_soup',
    name: '紫菜蛋花汤',
    type: 'soup',
    tags: ['quick', 'easy'],
    season: [],
    estimatedTime: 10,
    servings: 2,
    ingredientsNeeded: [
      { name: '紫菜', qty: 5, unit: 'g' },
      { name: '鸡蛋', qty: 1, unit: '个' }
    ],
    checklist: {
      mainIngredients: ['紫菜 5g', '鸡蛋 1个', '小葱 1根'],
      seasonings: ['盐', '香油', '白胡椒粉', '虾皮(可选)'],
      tools: ['汤锅', '汤勺']
    },
    timelineSteps: [
      { time: '00:00', action: '紫菜撕小块，鸡蛋打散，葱切花', type: 'prep' },
      { time: '03:00', action: '锅中加水烧开，放紫菜虾皮', type: 'cook', timer: 4 },
      { time: '07:00', action: '转小火淋入蛋液形成蛋花', type: 'cook', timer: 1 },
      { time: '09:00', action: '加盐白胡椒，淋香油撒葱花出锅', type: 'cook' }
    ],
    tip: '蛋液要在小火时淋入，蛋花才漂亮不散。'
  },
  {
    _id: 'recipe_tomato_egg_soup',
    name: '番茄鸡蛋汤',
    type: 'soup',
    tags: ['quick', 'easy'],
    season: [],
    estimatedTime: 12,
    servings: 2,
    ingredientsNeeded: [
      { name: '番茄', qty: 1, unit: '个' },
      { name: '鸡蛋', qty: 1, unit: '个' }
    ],
    checklist: {
      mainIngredients: ['番茄 1个', '鸡蛋 1个', '小葱 1根'],
      seasonings: ['盐', '香油', '食用油', '白胡椒粉'],
      tools: ['汤锅', '汤勺']
    },
    timelineSteps: [
      { time: '00:00', action: '番茄切小块，鸡蛋打散', type: 'prep' },
      { time: '03:00', action: '少油下番茄炒出汁', type: 'cook', timer: 2 },
      { time: '05:00', action: '加水烧开煮2分钟', type: 'cook', timer: 3 },
      { time: '09:00', action: '淋蛋液成蛋花，加盐胡椒香油葱花', type: 'cook' }
    ],
    tip: '番茄先炒出汁，汤色才红润浓郁。'
  },
  {
    _id: 'recipe_winter_melon_rib_soup',
    name: '冬瓜排骨汤',
    type: 'soup',
    tags: ['feast'],
    season: [6, 7, 8, 9],
    estimatedTime: 60,
    servings: 3,
    ingredientsNeeded: [
      { name: '排骨', qty: 400, unit: 'g' },
      { name: '冬瓜', qty: 500, unit: 'g' }
    ],
    checklist: {
      mainIngredients: ['排骨 400g', '冬瓜 500g', '姜 4片', '葱 1根'],
      seasonings: ['料酒', '盐', '白胡椒粉'],
      tools: ['汤锅/砂锅', '汤勺']
    },
    timelineSteps: [
      { time: '00:00', action: '排骨冷水下锅加料酒焯水，撇去浮沫捞出', type: 'prep' },
      { time: '08:00', action: '排骨加姜片和足量热水，大火烧开', type: 'cook', timer: 5 },
      { time: '13:00', action: '转小火炖排骨', type: 'wait', timer: 35 },
      { time: '48:00', action: '下冬瓜块继续炖至透明', type: 'wait', timer: 10 },
      { time: '58:00', action: '加盐和白胡椒调味，撒葱花出锅', type: 'cook' }
    ],
    tip: '冬瓜后放，炖太久会化掉。'
  },
  {
    _id: 'recipe_corn_carrot_soup',
    name: '玉米胡萝卜排骨汤',
    type: 'soup',
    tags: ['easy', 'feast'],
    season: [7, 8, 9, 10],
    estimatedTime: 60,
    servings: 3,
    ingredientsNeeded: [
      { name: '排骨', qty: 400, unit: 'g' },
      { name: '玉米', qty: 1, unit: '根' },
      { name: '胡萝卜', qty: 1, unit: '根' }
    ],
    checklist: {
      mainIngredients: ['排骨 400g', '玉米 1根', '胡萝卜 1根', '姜 3片'],
      seasonings: ['料酒', '盐'],
      tools: ['汤锅/砂锅', '汤勺']
    },
    timelineSteps: [
      { time: '00:00', action: '排骨焯水；玉米切段，胡萝卜切滚刀块', type: 'prep' },
      { time: '08:00', action: '所有食材加姜片和足量热水，大火烧开', type: 'cook', timer: 5 },
      { time: '13:00', action: '转小火慢炖', type: 'wait', timer: 45 },
      { time: '58:00', action: '加盐调味出锅', type: 'cook' }
    ],
    tip: '一次加足水，中途加水会冲淡汤味。'
  },
  {
    _id: 'recipe_hot_sour_soup',
    name: '酸辣汤',
    type: 'soup',
    tags: ['easy'],
    season: [],
    estimatedTime: 15,
    servings: 2,
    ingredientsNeeded: [
      { name: '豆腐', qty: 100, unit: 'g' },
      { name: '木耳', qty: 5, unit: 'g' },
      { name: '鸡蛋', qty: 1, unit: '个' }
    ],
    checklist: {
      mainIngredients: ['嫩豆腐 100g', '泡发木耳 5g', '火腿丝 少许', '鸡蛋 1个', '香菜 1根'],
      seasonings: ['陈醋', '白胡椒粉', '生抽', '淀粉', '盐', '香油'],
      tools: ['汤锅', '汤勺']
    },
    timelineSteps: [
      { time: '00:00', action: '豆腐木耳火腿切丝，鸡蛋打散，淀粉加水调水淀粉', type: 'prep' },
      { time: '05:00', action: '锅中加水烧开，下豆腐木耳火腿煮2分钟', type: 'cook', timer: 3 },
      { time: '09:00', action: '加生抽醋胡椒盐调味，淋水淀粉勾芡', type: 'cook', timer: 2 },
      { time: '12:00', action: '淋蛋液成蛋花，撒香菜淋香油出锅', type: 'cook' }
    ],
    tip: '酸辣比例按口味调，勾芡后汤才挂味。'
  }
];

module.exports = { recipes };
