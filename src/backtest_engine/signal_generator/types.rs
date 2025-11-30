/// 信号生成器内部使用的类型定义
/// 这些类型用于 nom 解析器和条件评估，不需要从 Python 传递

#[derive(Debug, Clone)]
pub enum CompareOp {
    GT,  // >
    LT,  // <
    GE,  // >=
    LE,  // <=
    EQ,  // ==
    NE,  // !=
    CGT, // > 交叉
    CLT, // < 交叉
    CGE, // >= 交叉
    CLE, // <= 交叉
    CEQ, // == 交叉
    CNE, // != 交叉
}

#[derive(Debug, Clone, PartialEq)]
pub enum OffsetType {
    Single(u32),
    RangeAnd(u32, u32), // &start-end：范围内所有值都必须满足
    RangeOr(u32, u32),  // |start-end：范围内任一值满足即可
    ListAnd(Vec<u32>),  // &val1/val2/val3：列表中所有值都必须满足
    ListOr(Vec<u32>),   // |val1/val2/val3：列表中任一值满足即可
}

#[derive(Debug, Clone)]
pub struct SignalDataOperand {
    pub name: String,
    pub source: String,
    pub offset: OffsetType,
}

#[derive(Debug, Clone)]
pub struct ParamOperand {
    pub name: String,
}

#[derive(Debug, Clone)]
pub enum SignalRightOperand {
    Data(SignalDataOperand),
    Param(ParamOperand),
    Scalar(f64),
}

#[derive(Debug, Clone)]
pub struct SignalCondition {
    pub negated: bool,
    pub left: SignalDataOperand,
    pub right: SignalRightOperand,
    pub op: CompareOp,
}
