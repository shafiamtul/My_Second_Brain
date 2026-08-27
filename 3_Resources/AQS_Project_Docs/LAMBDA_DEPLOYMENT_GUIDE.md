# 🚀 FULLY AUTOMATED LAMBDA DEPLOYMENT PIPELINE

**Status:** Ready to Execute  
**Deployment Model:** Fully Touchless / Headless CI/CD  
**Trigger:** Git push → CloudFormation → Lambda → CloudFront (automatic)  
**Time to Live:** ~15 minutes (after setup)

---

## Overview

This is a complete **Infrastructure-as-Code** + **Continuous Deployment** pipeline that automates **every step** from code commit to live production API. Zero manual SSH, zero human touchpoints.

### Components
1. **template.yaml** — SAM template defining Lambda + API Gateway + CloudWatch
2. **buildspec.yml** — CodeBuild automation (build → package → deploy → verify)
3. **CodePipeline** — Git trigger → CodeBuild → Deploy (auto)
4. **CloudFront** — Auto-updated to point to new API Gateway endpoint

---

## Setup Steps (One-Time)

### Step 1: Create CodeBuild Project

```bash
aws codebuild create-project \
  --name aqs-nextjs-api-build \
  --region us-east-1 \
  --profile aqs-automation \
  --source type=GITHUB,location=https://github.com/[YOUR_REPO].git,gitCloneDepth=1 \
  --environment type=LINUX_CONTAINER,image=aws/codebuild/standard:7.0,computeType=BUILD_GENERAL1_MEDIUM \
  --service-role arn:aws:iam::706922780929:role/CodeBuildServiceRole \
  --artifacts type=S3,location=aqs-dev-frontend-artifacts-706922780929 \
  --logs-config cloudWatchLogs={status=ENABLED,groupName=/aws/codebuild/aqs-nextjs-api}
```

### Step 2: Create IAM Role for CodeBuild

```bash
# Create trust policy
cat > trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "codebuild.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
  --role-name CodeBuildServiceRole \
  --assume-role-policy-document file://trust-policy.json \
  --region us-east-1 \
  --profile aqs-automation

# Attach policies
aws iam attach-role-policy \
  --role-name CodeBuildServiceRole \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess \
  --region us-east-1 \
  --profile aqs-automation
```

### Step 3: Create S3 Artifact Bucket

```bash
aws s3 mb s3://aqs-dev-frontend-artifacts-706922780929 \
  --region us-east-1 \
  --profile aqs-automation

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket aqs-dev-frontend-artifacts-706922780929 \
  --versioning-configuration Status=Enabled \
  --region us-east-1 \
  --profile aqs-automation
```

### Step 4: Create CodePipeline (GitHub → CodeBuild → Deploy)

```bash
# Create pipeline configuration
cat > pipeline.json << 'EOF'
{
  "pipeline": {
    "name": "aqs-nextjs-api-pipeline",
    "roleArn": "arn:aws:iam::706922780929:role/CodePipelineServiceRole",
    "artifactStore": {
      "type": "S3",
      "location": "aqs-dev-frontend-artifacts-706922780929"
    },
    "stages": [
      {
        "name": "Source",
        "actions": [
          {
            "name": "SourceAction",
            "actionTypeId": {
              "category": "Source",
              "owner": "ThirdParty",
              "provider": "GitHub",
              "version": "1"
            },
            "configuration": {
              "Owner": "[YOUR_GITHUB_OWNER]",
              "Repo": "[YOUR_REPO_NAME]",
              "Branch": "main",
              "OAuthToken": "[YOUR_GITHUB_TOKEN]"
            },
            "outputArtifacts": [
              {
                "name": "SourceOutput"
              }
            ]
          }
        ]
      },
      {
        "name": "Build",
        "actions": [
          {
            "name": "BuildAction",
            "actionTypeId": {
              "category": "Build",
              "owner": "AWS",
              "provider": "CodeBuild",
              "version": "1"
            },
            "configuration": {
              "ProjectName": "aqs-nextjs-api-build"
            },
            "inputArtifacts": [
              {
                "name": "SourceOutput"
              }
            ],
            "outputArtifacts": [
              {
                "name": "BuildOutput"
              }
            ]
          }
        ]
      }
    ]
  }
}
EOF

# Create the pipeline
aws codepipeline create-pipeline \
  --cli-input-json file://pipeline.json \
  --region us-east-1 \
  --profile aqs-automation
```

### Step 5: Create IAM Role for CodePipeline

```bash
cat > codepipeline-trust.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "codepipeline.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

aws iam create-role \
  --role-name CodePipelineServiceRole \
  --assume-role-policy-document file://codepipeline-trust.json \
  --region us-east-1 \
  --profile aqs-automation

aws iam attach-role-policy \
  --role-name CodePipelineServiceRole \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess \
  --region us-east-1 \
  --profile aqs-automation
```

---

## Deployment (After Setup Complete)

### Automatic Deployment (Recommended)
```bash
# Just push to main branch
git add .
git commit -m "Deploy Next.js API to Lambda"
git push origin main

# CodePipeline automatically triggers:
# 1. Pulls code from GitHub
# 2. CodeBuild builds & packages
# 3. Lambda updated
# 4. CloudFront origin updated
# 5. Live in 15 minutes
```

### Manual Deployment (Testing)
```bash
# Trigger build manually
aws codebuild start-build \
  --project-name aqs-nextjs-api-build \
  --region us-east-1 \
  --profile aqs-automation

# Watch the build
aws codebuild batch-get-builds \
  --ids $(aws codebuild start-build --project-name aqs-nextjs-api-build --query 'build.id' --output text --region us-east-1 --profile aqs-automation) \
  --region us-east-1 \
  --profile aqs-automation \
  --query 'builds[0].buildStatus' \
  --output text
```

---

## What Happens During Deployment

### Timeline (Automatic)
1. **T+0s** — Git push detected
2. **T+10s** — CodePipeline triggers
3. **T+20s** — CodeBuild starts
   - npm ci (install deps)
   - npm run build (Next.js compile)
   - Package for Lambda
   - Upload to S3
4. **T+180s** — SAM template deployed
   - Lambda function created/updated
   - API Gateway created/updated
5. **T+200s** — Lambda code updated
   - New version deployed
   - All previous versions kept for rollback
6. **T+220s** — CloudFront origin updated
   - Distribution begins propagating (2-5 min)
7. **T+300s+** — API live on atlasquantsystems.com

### Verification Automated
- ✅ Lambda responding
- ✅ API Gateway routing
- ✅ CloudFront delivering
- ✅ Health check passed

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                      Git Repository                          │
│                  (push to main branch)                        │
└─────────────────────┬──────────────────────────────────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │   AWS CodePipeline    │
          │  (Automated Trigger)  │
          └───────────┬───────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │    AWS CodeBuild      │
          │  ┌─────────────────┐  │
          │  │ npm ci          │  │
          │  │ npm run build   │  │
          │  │ Package Lambda  │  │
          │  │ Deploy SAM      │  │
          │  └─────────────────┘  │
          └───────────┬───────────┘
                      │
           ┌──────────┴──────────┬──────────┐
           ▼                     ▼          ▼
      ┌─────────┐         ┌──────────┐  ┌──────┐
      │  Lambda │         │ API Gate │  │ S3   │
      │  Func   │◄────────┤  way     │  │ Arti │
      │         │         │          │  │ fact │
      └────┬────┘         └──────────┘  └──────┘
           │
           └────────────────┐
                            ▼
                  ┌──────────────────┐
                  │    CloudFront    │
                  │  E14OIXL39MD9NW  │
                  └────────┬─────────┘
                           │
                  https://atlasquantsystems.com
```

---

## Monitoring & Alerts

### CloudWatch Dashboards (Auto-Created)
- Lambda error rate
- Lambda duration (should be <1s warm, <3s cold)
- API Gateway 5xx errors
- DynamoDB throttling

### Automatic Alarms
- Lambda errors > 5 → SNS alert
- Lambda duration > 5s → SNS alert
- API Gateway 5xx > 10 → SNS alert

### View Logs
```bash
# CodeBuild logs
aws logs tail /aws/codebuild/aqs-nextjs-api --follow \
  --region us-east-1 \
  --profile aqs-automation

# Lambda logs
aws logs tail /aws/lambda/aqs-nextjs-api --follow \
  --region us-east-1 \
  --profile aqs-automation

# API Gateway logs
aws logs tail /aws/apigateway/aqs-nextjs-api --follow \
  --region us-east-1 \
  --profile aqs-automation
```

---

## Rollback (Automatic)

### Rollback to Previous Lambda Version
```bash
# List versions
aws lambda list-versions-by-function \
  --function-name aqs-nextjs-api \
  --region us-east-1 \
  --profile aqs-automation

# Rollback to specific version
aws lambda update-alias \
  --function-name aqs-nextjs-api \
  --name live \
  --function-version [PREVIOUS_VERSION] \
  --region us-east-1 \
  --profile aqs-automation
```

### Rollback CodePipeline
```bash
# Execute previous successful stage
aws codepipeline start-pipeline-execution \
  --pipeline-name aqs-nextjs-api-pipeline \
  --region us-east-1 \
  --profile aqs-automation
```

---

## Cost Estimation

| Component | Cost | Notes |
|-----------|------|-------|
| Lambda | $0.20-0.50/mo | ~1M requests/month @ <1s |
| API Gateway | $3.50/mo | ~1M requests/month |
| CloudFront | $0.085/GB | Minimal (JSON only) |
| CloudWatch | $0.30/mo | Logs + alarms |
| S3 (artifacts) | <$1/mo | Versioning enabled |
| **Total** | **~$5-10/mo** | Fully serverless, auto-scaling |

---

## Success Criteria ✅

After deployment, verify:

```bash
# 1. API responds with JSON
curl https://atlasquantsystems.com/api/market-snapshot | jq .

# 2. Response time <500ms
time curl -s https://atlasquantsystems.com/api/market-snapshot > /dev/null

# 3. Browser loads (no HTML 502/504)
open https://atlasquantsystems.com

# 4. CloudWatch shows Lambda invocations
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=aqs-nextjs-api \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum \
  --region us-east-1 \
  --profile aqs-automation
```

---

## Files

1. **template.yaml** — SAM CloudFormation template
2. **buildspec.yml** — CodeBuild automation script
3. This file — Setup & deployment guide

---

## Troubleshooting

### CodeBuild Fails
```bash
# Check build logs
aws codebuild batch-get-builds \
  --ids [BUILD_ID] \
  --query 'builds[0].logs' \
  --region us-east-1 \
  --profile aqs-automation
```

### Lambda Not Responding
```bash
# Check Lambda logs
aws logs tail /aws/lambda/aqs-nextjs-api --follow \
  --region us-east-1 \
  --profile aqs-automation

# Test Lambda directly
aws lambda invoke \
  --function-name aqs-nextjs-api \
  --payload '{"httpMethod":"GET","path":"/api/market-snapshot","headers":{}}' \
  --region us-east-1 \
  --profile aqs-automation \
  /tmp/response.json

cat /tmp/response.json
```

### CloudFront Not Updated
```bash
# Check CloudFront status
aws cloudfront get-distribution \
  --id E14OIXL39MD9NW \
  --region us-east-1 \
  --profile aqs-automation \
  --query 'Distribution.Status'
```

---

## Next Steps

1. **Create GitHub Personal Access Token** (if not exists)
   - GitHub Settings → Developer settings → Personal access tokens
   - Scope: `repo`, `admin:repo_hook`

2. **Run Setup Steps Above** (one-time)
   - Takes ~15 minutes

3. **Test with Git Push**
   - Update a file in public-site/
   - Commit & push to main
   - Watch CodePipeline in AWS console

4. **Verify Live**
   - Open https://atlasquantsystems.com
   - Check API responses in DevTools

**Ready to go fully automated. Execute setup steps whenever ready.**
