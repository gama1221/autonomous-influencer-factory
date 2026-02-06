terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.11"
    }
    vault = {
      source  = "hashicorp/vault"
      version = "~> 3.22"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }

  backend "s3" {
    bucket         = "chimera-terraform-state"
    key            = "chimera-factory/production/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "chimera-terraform-locks"
  }
}

# Provider Configuration
provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "chimera-factory"
      Environment = var.environment
      ManagedBy   = "terraform"
      Owner       = "ai-platform-team"
      CostCenter  = "ai-research-001"
    }
  }
}

provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
  token                  = data.aws_eks_cluster_auth.this.token
}

provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
    token                  = data.aws_eks_cluster_auth.this.token
  }
}

provider "vault" {
  address = var.vault_address
  token   = var.vault_token
  namespace = var.vault_namespace
}

data "aws_eks_cluster_auth" "this" {
  name = module.eks.cluster_name
}

data "aws_availability_zones" "available" {
  state = "available"
}

# Random Resources
resource "random_password" "database_password" {
  length  = 32
  special = false
}

resource "random_password" "redis_password" {
  length  = 32
  special = false
}

resource "random_password" "minio_root_password" {
  length  = 32
  special = false
}

resource "random_string" "bucket_suffix" {
  length  = 8
  special = false
  upper   = false
}

# VPC Module
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "chimera-${var.environment}"
  cidr = var.vpc_cidr

  azs             = slice(data.aws_availability_zones.available.names, 0, 3)
  private_subnets = var.private_subnets
  public_subnets  = var.public_subnets

  enable_nat_gateway   = true
  single_nat_gateway   = false
  enable_dns_hostnames = true
  enable_dns_support   = true

  # VPC Flow Logs
  enable_flow_log                      = true
  create_flow_log_cloudwatch_log_group = true
  create_flow_log_cloudwatch_iam_role  = true
  flow_log_max_aggregation_interval    = 60

  # VPC Endpoints
  enable_s3_endpoint              = true
  enable_dynamodb_endpoint        = true
  enable_ecr_api_endpoint         = true
  enable_ecr_dkr_endpoint         = true
  enable_secretsmanager_endpoint  = true
  enable_ssm_endpoint             = true

  tags = {
    "kubernetes.io/cluster/${local.cluster_name}" = "shared"
    "karpenter.sh/discovery" = local.cluster_name
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = "1"
    "karpenter.sh/discovery" = local.cluster_name
  }

  public_subnet_tags = {
    "kubernetes.io/role/elb" = "1"
  }
}

# EKS Cluster
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = local.cluster_name
  cluster_version = var.cluster_version

  cluster_endpoint_public_access  = true
  cluster_endpoint_private_access = true

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # EKS Managed Node Groups
  eks_managed_node_groups = {
    compute = {
      name           = "compute"
      instance_types = ["m6i.xlarge", "m6i.2xlarge"]
      min_size       = 1
      max_size       = 10
      desired_size   = 3

      labels = {
        node-type = "compute-optimized"
      }

      taints = []

      tags = {
        "k8s.io/cluster-autoscaler/enabled" = "true"
        "k8s.io/cluster-autoscaler/${local.cluster_name}" = "owned"
      }
    }

    memory = {
      name           = "memory"
      instance_types = ["r6i.xlarge", "r6i.2xlarge"]
      min_size       = 1
      max_size       = 5
      desired_size   = 2

      labels = {
        node-type = "memory-optimized"
      }

      tags = {
        "k8s.io/cluster-autoscaler/enabled" = "true"
        "k8s.io/cluster-autoscaler/${local.cluster_name}" = "owned"
      }
    }

    gpu = {
      name           = "gpu"
      instance_types = ["g4dn.xlarge", "g5.xlarge"]
      min_size       = 1
      max_size       = 4
      desired_size   = 2

      labels = {
        node-type    = "gpu"
        accelerator  = "nvidia-tesla-t4"
      }

      taints = [{
        key    = "nvidia.com/gpu"
        value  = "present"
        effect = "NO_SCHEDULE"
      }]

      tags = {
        "k8s.io/cluster-autoscaler/enabled" = "true"
        "k8s.io/cluster-autoscaler/${local.cluster_name}" = "owned"
      }
    }
  }

  cluster_addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent = true
    }
    aws-ebs-csi-driver = {
      most_recent = true
    }
    aws-efs-csi-driver = {
      most_recent = true
    }
  }

  # CloudWatch Logs
  cluster_enabled_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# Karpenter for node autoscaling
module "karpenter" {
  source  = "terraform-aws-modules/eks/aws//modules/karpenter"
  version = "~> 19.0"

  cluster_name = module.eks.cluster_name

  irsa_oidc_provider_arn          = module.eks.oidc_provider_arn
  irsa_namespace_service_accounts = ["karpenter:karpenter"]

  create_iam_role = false
  iam_role_arn    = module.eks.eks_managed_node_groups["compute"].iam_role_arn

  tags = {
    Environment = var.environment
  }
}

resource "helm_release" "karpenter" {
  namespace        = "karpenter"
  create_namespace = true

  name       = "karpenter"
  repository = "https://charts.karpenter.sh"
  chart      = "karpenter"
  version    = "0.32.1"

  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = module.karpenter.irsa_arn
  }

  set {
    name  = "clusterName"
    value = module.eks.cluster_name
  }

  set {
    name  = "clusterEndpoint"
    value = module.eks.cluster_endpoint
  }

  set {
    name  = "aws.defaultInstanceProfile"
    value = module.karpenter.instance_profile_name
  }
}

# RDS PostgreSQL Database
module "rds" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 6.0"

  identifier = "chimera-${var.environment}"

  engine               = "postgres"
  engine_version       = "15.3"
  family               = "postgres15"
  major_engine_version = "15"
  instance_class       = "db.m6i.xlarge"

  allocated_storage     = 100
  max_allocated_storage = 500
  storage_encrypted     = true
  storage_type          = "gp3"

  db_name  = "chimera"
  username = "chimera_admin"
  password = random_password.database_password.result
  port     = 5432

  multi_az               = true
  db_subnet_group_name   = module.vpc.database_subnet_group_name
  vpc_security_group_ids = [module.rds_security_group.security_group_id]

  maintenance_window      = "Mon:03:00-Mon:04:00"
  backup_window           = "04:00-05:00"
  backup_retention_period = 7
  skip_final_snapshot     = false
  final_snapshot_identifier_prefix = "chimera-final"

  # Enhanced Monitoring
  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_enhanced_monitoring.arn

  # Performance Insights
  performance_insights_enabled          = true
  performance_insights_retention_period = 7
  performance_insights_kms_key_id       = aws_kms_key.rds.arn

  parameters = [
    {
      name  = "shared_preload_libraries"
      value = "pg_stat_statements"
    },
    {
      name  = "pg_stat_statements.track"
      value = "all"
    },
    {
      name  = "pg_stat_statements.max"
      value = "10000"
    },
    {
      name  = "track_activity_query_size"
      value = "4096"
    },
    {
      name  = "log_min_duration_statement"
      value = "1000"
    }
  ]

  tags = {
    Environment = var.environment
    Component   = "database"
  }
}

# ElastiCache Redis
resource "aws_elasticache_replication_group" "chimera" {
  replication_group_id          = "chimera-${var.environment}"
  description                   = "Chimera Factory Redis Cluster"
  node_type                     = "cache.m6g.xlarge"
  port                          = 6379
  parameter_group_name          = "default.redis7"
  engine_version                = "7.0"
  transit_encryption_enabled    = true
  at_rest_encryption_enabled    = true
  automatic_failover_enabled    = true
  multi_az_enabled              = true
  num_cache_clusters            = 3
  security_group_ids            = [module.redis_security_group.security_group_id]
  subnet_group_name             = aws_elasticache_subnet_group.chimera.name
  snapshot_retention_limit      = 7
  snapshot_window               = "05:00-06:00"
  maintenance_window            = "sun:03:00-sun:04:00"

  tags = {
    Environment = var.environment
    Component   = "cache"
  }
}

resource "aws_elasticache_subnet_group" "chimera" {
  name       = "chimera-${var.environment}"
  subnet_ids = module.vpc.private_subnets
}

# S3 Buckets
resource "aws_s3_bucket" "terraform_state" {
  bucket = "chimera-terraform-state"
  tags = {
    Environment = var.environment
    Purpose     = "terraform-state"
  }
}

resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket" "media_storage" {
  bucket = "chimera-media-${var.environment}-${random_string.bucket_suffix.result}"
  tags = {
    Environment = var.environment
    Purpose     = "media-storage"
  }
}

resource "aws_s3_bucket_versioning" "media_storage" {
  bucket = aws_s3_bucket.media_storage.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "media_storage" {
  bucket = aws_s3_bucket.media_storage.id

  rule {
    id     = "archive-to-glacier"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = 365
    }
  }
}

# ECR Repositories
resource "aws_ecr_repository" "api" {
  name                 = "chimera-api"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Environment = var.environment
    Component   = "api"
  }
}

resource "aws_ecr_repository" "agent" {
  name                 = "chimera-agent"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Environment = var.environment
    Component   = "agent"
  }
}

resource "aws_ecr_repository_policy" "push_pull" {
  repository = aws_ecr_repository.api.name
  policy     = <<EOF
{
  "Version": "2008-10-17",
  "Statement": [
    {
      "Sid": "AllowPushPull",
      "Effect": "Allow",
      "Principal": {
        "AWS": [
          "${module.eks.eks_managed_node_groups["compute"].iam_role_arn}",
          "${module.eks.eks_managed_node_groups["memory"].iam_role_arn}",
          "${module.eks.eks_managed_node_groups["gpu"].iam_role_arn}"
        ]
      },
      "Action": [
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:BatchCheckLayerAvailability",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload"
      ]
    }
  ]
}
EOF
}

# IAM Roles and Policies
resource "aws_iam_role" "rds_enhanced_monitoring" {
  name = "chimera-rds-enhanced-monitoring"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })

  managed_policy_arns = [
    "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
  ]
}

resource "aws_iam_policy" "chimera_secrets_access" {
  name        = "chimera-secrets-access"
  description = "Policy for accessing secrets in AWS Secrets Manager"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:chimera/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "eks_node_secrets" {
  role       = module.eks.eks_managed_node_groups["compute"].iam_role_name
  policy_arn = aws_iam_policy.chimera_secrets_access.arn
}

# Security Groups
module "rds_security_group" {
  source  = "terraform-aws-modules/security-group/aws"
  version = "~> 5.0"

  name        = "chimera-rds"
  description = "Security group for RDS PostgreSQL"
  vpc_id      = module.vpc.vpc_id

  ingress_with_cidr_blocks = [
    {
      rule        = "postgresql-tcp"
      cidr_blocks = module.vpc.vpc_cidr_block
      description = "PostgreSQL access from VPC"
    }
  ]

  egress_with_cidr_blocks = [
    {
      rule        = "all-all"
      cidr_blocks = "0.0.0.0/0"
      description = "Outbound access"
    }
  ]

  tags = {
    Environment = var.environment
    Component   = "database"
  }
}

module "redis_security_group" {
  source  = "terraform-aws-modules/security-group/aws"
  version = "~> 5.0"

  name        = "chimera-redis"
  description = "Security group for ElastiCache Redis"
  vpc_id      = module.vpc.vpc_id

  ingress_with_cidr_blocks = [
    {
      rule        = "redis-tcp"
      cidr_blocks = module.vpc.vpc_cidr_block
      description = "Redis access from VPC"
    }
  ]

  egress_with_cidr_blocks = [
    {
      rule        = "all-all"
      cidr_blocks = "0.0.0.0/0"
      description = "Outbound access"
    }
  ]

  tags = {
    Environment = var.environment
    Component   = "cache"
  }
}

# KMS Keys
resource "aws_kms_key" "rds" {
  description             = "KMS key for RDS encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Environment = var.environment
    Purpose     = "rds-encryption"
  }
}

resource "aws_kms_key" "s3" {
  description             = "KMS key for S3 encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Environment = var.environment
    Purpose     = "s3-encryption"
  }
}

resource "aws_kms_alias" "rds" {
  name          = "alias/chimera-rds-${var.environment}"
  target_key_id = aws_kms_key.rds.key_id
}

resource "aws_kms_alias" "s3" {
  name          = "alias/chimera-s3-${var.environment}"
  target_key_id = aws_kms_key.s3.key_id
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "chimera" {
  name              = "/aws/eks/chimera/${var.environment}"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.s3.arn

  tags = {
    Environment = var.environment
    Component   = "logging"
  }
}

resource "aws_cloudwatch_log_group" "application" {
  name              = "/chimera/application/${var.environment}"
  retention_in_days = 90
  kms_key_id        = aws_kms_key.s3.arn

  tags = {
    Environment = var.environment
    Component   = "application-logs"
  }
}

# Route53 DNS Records
resource "aws_route53_zone" "chimera" {
  name = "chimera.example.com"
  tags = {
    Environment = var.environment
  }
}

resource "aws_route53_record" "api" {
  zone_id = aws_route53_zone.chimera.zone_id
  name    = "api.${aws_route53_zone.chimera.name}"
  type    = "A"

  alias {
    name                   = module.eks.cluster_ingress_endpoint
    zone_id                = module.eks.cluster_hosted_zone_id
    evaluate_target_health = true
  }
}

resource "aws_route