resource "aws_s3_bucket" "devops_demo" {
  bucket_prefix = "local-devops-demo-"

  tags = {
    Name        = "local-devops-demo"
    Environment = "dev"
    ManagedBy   = "Terraform"
  }
}

resource "aws_s3_bucket_versioning" "devops_demo" {
  bucket = aws_s3_bucket.devops_demo.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "devops_demo" {
  bucket = aws_s3_bucket.devops_demo.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}